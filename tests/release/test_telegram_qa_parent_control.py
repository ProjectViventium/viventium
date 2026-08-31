from __future__ import annotations

import base64
import importlib.util
import json
import os
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from qa_control_test_support import write_artifact_identity

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "viventium" / "telegram_qa_parent_control.py"
SESSION_SCRIPT = ROOT / "scripts" / "viventium" / "local_qa_runtime_control.py"
CLI = ROOT / "bin" / "viventium"
LAUNCHER = ROOT / "viventium_v0_4" / "viventium-librechat-start.sh"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def fixture(tmp_path: Path):
    session = load(SESSION_SCRIPT, "local_qa_runtime_control")
    installed = tmp_path / "installed"
    installed.mkdir()
    runtime = tmp_path / "runtime"
    state = runtime / "local-qa" / "active.json"
    identity = runtime / "parallel-work-artifact-identity.json"
    request = runtime / "parallel-work-local-qa-request.json"
    write_artifact_identity(installed, identity)
    request.write_text(
        '{"contractVersion":1,"mode":"local-qa","requested":true}\n',
        encoding="utf-8",
    )
    os.chmod(request, 0o600)
    now = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)
    redacted = session.activate_session(
        state_path=state,
        installed_root=installed,
        artifact_identity_path=identity,
        local_qa_request_path=request,
        case_id="TR-026",
        expires_in_seconds=900,
        now=now,
        token_bytes=lambda size: b"s" * size,
    )
    token = base64.urlsafe_b64encode(b"s" * 32).decode().rstrip("=")
    return installed, runtime, state, identity, request, now, redacted, token


class FakeControl:
    def __init__(self):
        self.calls = []

    def arm_tr026_control(self, **kwargs):
        self.calls.append(("arm", kwargs))
        return {
            "case_id": "TR-026",
            "artifact_ref": "b" * 16,
            "delay_ms": 280,
            "expires_at_ms": 1787500860000,
            "session_ref": kwargs["session_ref"],
        }

    def read_redacted_audit(self, **kwargs):
        self.calls.append(("audit", kwargs))
        return [{"outcome": "claimed", "delay_ms": 280}]

    def cleanup_tr026_control(self, **kwargs):
        self.calls.append(("cleanup", kwargs))
        return True


def test_arm_uses_canonical_private_token_and_prints_only_redacted_receipt(
    tmp_path: Path,
) -> None:
    module = load(SCRIPT, "telegram_qa_parent_control")
    installed, runtime, state, identity, request, now, redacted, token = fixture(tmp_path)
    fake = FakeControl()

    result = module.arm_telegram_race(
        state_path=state,
        installed_root=installed,
        artifact_identity_path=identity,
        local_qa_request_path=request,
        telegram_state_dir=runtime / "telegram",
        owner_user_id=91,
        chat_id=-100700,
        thread_id=31,
        stale_source_sequence=7001,
        source_sequence=7002,
        update_id=880002,
        ttl_seconds=120,
        now=now + timedelta(seconds=1),
        control_module=fake,
    )

    assert result == {
        "armed": True,
        "artifactRef": "b" * 16,
        "delayMs": 280,
        "sessionRef": redacted["sessionRef"],
    }
    call = fake.calls[0][1]
    assert call["case_token"] == token
    assert call["session_ref"] == redacted["sessionRef"]
    assert call["owner_user_id"] == 91
    assert token not in json.dumps(result)


def test_wrong_candidate_or_expired_session_cannot_arm(tmp_path: Path) -> None:
    module = load(SCRIPT, "telegram_qa_parent_control_reject")
    installed, runtime, state, identity, request, now, _, _ = fixture(tmp_path)
    common = {
        "state_path": state,
        "installed_root": installed,
        "artifact_identity_path": identity,
        "local_qa_request_path": request,
        "telegram_state_dir": runtime / "telegram",
        "owner_user_id": 91,
        "chat_id": -100700,
        "thread_id": 31,
        "stale_source_sequence": 7001,
        "source_sequence": 7002,
        "update_id": 880002,
        "ttl_seconds": 120,
        "control_module": FakeControl(),
    }
    with pytest.raises(ValueError, match="expired"):
        module.arm_telegram_race(now=now + timedelta(minutes=16), **common)
    other = runtime / "other"
    other.mkdir()
    with pytest.raises(ValueError, match="candidate"):
        module.arm_telegram_race(now=now, **{**common, "installed_root": other})


def test_audit_and_cleanup_use_canonical_token_and_cleanup_survives_expiry(
    tmp_path: Path,
) -> None:
    module = load(SCRIPT, "telegram_qa_parent_control_cleanup")
    installed, runtime, state, identity, _, _, redacted, token = fixture(tmp_path)
    fake = FakeControl()
    common = {
        "state_path": state,
        "installed_root": installed,
        "artifact_identity_path": identity,
        "telegram_state_dir": runtime / "telegram",
        "control_module": fake,
    }
    audit = module.audit_telegram_race(**common)
    assert audit == {
        "caseId": "TR-026",
        "evidence": [{"outcome": "claimed", "delay_ms": 280}],
        "sessionRef": redacted["sessionRef"],
    }
    assert token not in json.dumps(audit)

    identity.write_text('{"candidate":"replaced-after-arm"}\n', encoding="utf-8")
    result = module.cleanup_telegram_race(**common)
    assert result == {"cleaned": True, "sessionRef": redacted["sessionRef"]}
    assert fake.calls[-1][1]["case_token"] == token
    assert fake.calls[-1][1]["session_ref"] == redacted["sessionRef"]


def test_cleanup_is_a_safe_noop_for_another_case(tmp_path: Path) -> None:
    session = load(SESSION_SCRIPT, "local_qa_runtime_control_other")
    module = load(SCRIPT, "telegram_qa_parent_control_other")
    installed = tmp_path / "installed"
    installed.mkdir()
    runtime = tmp_path / "runtime"
    identity = runtime / "parallel-work-artifact-identity.json"
    request = runtime / "parallel-work-local-qa-request.json"
    state = runtime / "local-qa" / "active.json"
    write_artifact_identity(installed, identity)
    request.write_text(
        '{"contractVersion":1,"mode":"local-qa","requested":true}\n', encoding="utf-8"
    )
    os.chmod(request, 0o600)
    session.activate_session(
        state_path=state,
        installed_root=installed,
        artifact_identity_path=identity,
        local_qa_request_path=request,
        case_id="EMO-UC-048",
        expires_in_seconds=900,
    )
    assert module.cleanup_telegram_race(
        state_path=state,
        installed_root=installed,
        artifact_identity_path=identity,
        telegram_state_dir=runtime / "telegram",
        control_module=FakeControl(),
    ) == {"cleaned": False}


def test_parent_cli_uses_adapter_and_launcher_carries_canonical_contract() -> None:
    cli = CLI.read_text(encoding="utf-8")
    launcher = LAUNCHER.read_text(encoding="utf-8")
    assert "arm-telegram-race" in cli
    assert "audit-telegram-race" in cli
    assert "cleanup-telegram-race" in cli
    assert "telegram_qa_parent_control.py" in cli
    assert "VIVENTIUM_LOCAL_QA_CASE_TOKEN" in launcher
    assert "VIVENTIUM_LOCAL_QA_CASE_ID" in launcher
    assert "VIVENTIUM_LOCAL_QA_SESSION_REF" in launcher
    assert (
        "    VIVENTIUM_APP_SUPPORT_DIR\n"
        "    VIVENTIUM_TELEGRAM_LOCAL_QA_MODE\n"
    ) in launcher
    assert "arm-telegram-race < private-tr026-scope.json" in cli
    assert (
        "Supported cases: TR-026, EMO-UC-047, EMO-UC-048, MPV-061, "
        "PWK-UC-015, PWK-UC-016, PWK-UC-017, REL-UC-004."
    ) in cli
    assert "--owner-user-id" not in cli


def test_private_scope_parser_is_exact_and_bounded() -> None:
    module = load(SCRIPT, "telegram_qa_parent_control_scope")
    scope = {
        "caseId": "TR-026",
        "chatId": -100700,
        "contractVersion": 1,
        "ownerUserId": 91,
        "sourceSequence": 7002,
        "staleSourceSequence": 7001,
        "threadId": 31,
        "ttlSeconds": 120,
        "updateId": 880002,
    }
    assert module.parse_private_scope(json.dumps(scope)) == scope
    with pytest.raises(ValueError, match="scope"):
        module.parse_private_scope(json.dumps({**scope, "extra": True}))
    with pytest.raises(ValueError, match="scope"):
        module.parse_private_scope("x" * 4097)
    with pytest.raises(ValueError, match="scope"):
        module.parse_private_scope('{"caseId":"TR-026","caseId":"TR-026"}')
    with pytest.raises(ValueError, match="scope"):
        module.parse_private_scope(b"\xff")


def test_parent_adapter_matches_the_real_telegram_component_api(tmp_path: Path) -> None:
    session = load(SESSION_SCRIPT, "local_qa_runtime_control_real_component")
    module = load(SCRIPT, "telegram_qa_parent_control_real_component")
    installed = tmp_path / "installed"
    component_relative = Path(
        "viventium_v0_4/telegram-viventium/TelegramVivBot/utils/tr026_local_qa.py"
    )
    component_path = installed / component_relative
    component_path.parent.mkdir(parents=True)
    shutil.copy2(ROOT / component_relative, component_path)
    runtime = tmp_path / "runtime"
    state = runtime / "local-qa" / "active.json"
    identity = runtime / "parallel-work-artifact-identity.json"
    request = runtime / "parallel-work-local-qa-request.json"
    write_artifact_identity(installed, identity)
    request.write_text(
        '{"contractVersion":1,"mode":"local-qa","requested":true}\n', encoding="utf-8"
    )
    os.chmod(request, 0o600)
    now = datetime.now(timezone.utc)
    session.activate_session(
        state_path=state,
        installed_root=installed,
        artifact_identity_path=identity,
        local_qa_request_path=request,
        case_id="TR-026",
        expires_in_seconds=900,
        now=now,
        token_bytes=lambda size: b"r" * size,
    )
    result = module.arm_telegram_race(
        state_path=state,
        installed_root=installed,
        artifact_identity_path=identity,
        local_qa_request_path=request,
        telegram_state_dir=runtime / "telegram",
        owner_user_id=91,
        chat_id=-100700,
        thread_id=31,
        stale_source_sequence=7001,
        source_sequence=7002,
        update_id=880002,
        ttl_seconds=120,
        now=now + timedelta(seconds=1),
    )
    assert result["armed"] is True
    assert result["delayMs"] == 280
    assert base64.urlsafe_b64encode(b"r" * 32).decode().rstrip("=") not in json.dumps(result)
    assert module.cleanup_telegram_race(
        state_path=state,
        installed_root=installed,
        artifact_identity_path=identity,
        telegram_state_dir=runtime / "telegram",
    )["cleaned"] is True

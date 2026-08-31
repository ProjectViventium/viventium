import asyncio
import base64
import hashlib
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

BOT_DIR = Path(__file__).resolve().parents[1] / "TelegramVivBot"
README = Path(__file__).resolve().parents[1] / "README.md"
CASE_ID_ENV = "VIVENTIUM_LOCAL_QA_CASE_ID"
CASE_TOKEN_ENV = "VIVENTIUM_LOCAL_QA_CASE_TOKEN"
SESSION_REF_ENV = "VIVENTIUM_LOCAL_QA_SESSION_REF"
CANONICAL_CASE_ID = "TR-026"
CANONICAL_TOKEN = base64.urlsafe_b64encode(b"t" * 32).decode().rstrip("=")
CANONICAL_SESSION_REF = (
    "qa_" + hashlib.sha256(CANONICAL_TOKEN.encode()).hexdigest()[:24]
)
OWNER_USER_ID = 12_345
if str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))

from utils.tr026_local_qa import (
    TR026_DELAY_MS,
    SyntheticTelegramSourceEvent,
    arm_tr026_control,
    cleanup_tr026_control,
    maybe_delay_tr026_core_ingestion,
    read_redacted_audit,
)


def _event(**overrides):
    values = {
        "update_id": 880_002,
        "chat_id": -100_700,
        "thread_id": 31,
        "source_sequence": 7_002,
        "owner_user_id": OWNER_USER_ID,
        "event_kind": "telegram_source",
    }
    values.update(overrides)
    return SyntheticTelegramSourceEvent(**values)


def _arm(state_dir, **overrides):
    values = {
        "state_dir": state_dir,
        "case_id": CANONICAL_CASE_ID,
        "case_token": CANONICAL_TOKEN,
        "session_ref": CANONICAL_SESSION_REF,
        "owner_user_id": OWNER_USER_ID,
        "chat_id": -100_700,
        "thread_id": 31,
        "stale_source_sequence": 7_001,
        "source_sequence": 7_002,
        "update_id": 880_002,
        "ttl_seconds": 120,
    }
    values.update(overrides)
    return arm_tr026_control(**values)


def _set_runtime_contract(monkeypatch):
    monkeypatch.setenv("VIVENTIUM_TELEGRAM_LOCAL_QA_MODE", "tr-026")
    monkeypatch.setenv(CASE_ID_ENV, CANONICAL_CASE_ID)
    monkeypatch.setenv(CASE_TOKEN_ENV, CANONICAL_TOKEN)
    monkeypatch.setenv(SESSION_REF_ENV, CANONICAL_SESSION_REF)


def _read_audit(
    state_dir, *, case_token=CANONICAL_TOKEN, session_ref=CANONICAL_SESSION_REF
):
    return read_redacted_audit(
        state_dir=state_dir,
        case_id=CANONICAL_CASE_ID,
        case_token=case_token,
        session_ref=session_ref,
    )


def test_arm_accepts_parent_contract_and_returns_only_redacted_refs(tmp_path):
    receipt = _arm(tmp_path)

    assert (
        receipt.artifact_ref
        == hashlib.sha256(CANONICAL_TOKEN.encode()).hexdigest()[:16]
    )
    assert receipt.session_ref == CANONICAL_SESSION_REF
    assert set(receipt.__dataclass_fields__) == {"artifact_ref", "session_ref"}
    assert receipt.case_id == CANONICAL_CASE_ID
    assert receipt.delay_ms == TR026_DELAY_MS
    plan_path = next((tmp_path / "local-qa" / "tr-026" / "armed").glob("*.json"))
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert plan["case_id"] == CANONICAL_CASE_ID
    assert plan["session_ref"] == CANONICAL_SESSION_REF
    assert plan["event"]["owner_user_id"] == OWNER_USER_ID
    assert plan["event"] == {
        "event_kind": "telegram_source",
        "owner_user_id": OWNER_USER_ID,
        "chat_id": -100_700,
        "thread_id": 31,
        "stale_source_sequence": 7_001,
        "source_sequence": 7_002,
        "update_id": 880_002,
    }
    assert (
        plan["case_token_sha256"]
        == hashlib.sha256(CANONICAL_TOKEN.encode()).hexdigest()
    )
    assert CANONICAL_TOKEN not in plan_path.read_text(encoding="utf-8")
    assert stat.S_IMODE(plan_path.stat().st_mode) == 0o600
    directories = [path for path in (tmp_path / "local-qa").rglob("*") if path.is_dir()]
    assert directories
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o700 for path in directories)


def test_parent_direct_api_uses_fixed_case_metadata_without_serializing_it(tmp_path):
    receipt = arm_tr026_control(
        state_dir=tmp_path,
        case_token=CANONICAL_TOKEN,
        session_ref=CANONICAL_SESSION_REF,
        owner_user_id=OWNER_USER_ID,
        chat_id=-100_700,
        thread_id=31,
        stale_source_sequence=7_001,
        source_sequence=7_002,
        update_id=880_002,
    )

    assert receipt.case_id == CANONICAL_CASE_ID
    assert receipt.delay_ms == 280
    assert set(receipt.__dataclass_fields__) == {"artifact_ref", "session_ref"}
    assert (
        cleanup_tr026_control(
            state_dir=tmp_path,
            case_token=CANONICAL_TOKEN,
            session_ref=CANONICAL_SESSION_REF,
        )
        is True
    )
    assert (
        read_redacted_audit(
            state_dir=tmp_path,
            case_token=CANONICAL_TOKEN,
            session_ref=CANONICAL_SESSION_REF,
        )[-1]["outcome"]
        == "cleaned"
    )


@pytest.mark.asyncio
async def test_runtime_requires_the_private_case_token(monkeypatch, tmp_path):
    _set_runtime_contract(monkeypatch)
    monkeypatch.delenv(CASE_TOKEN_ENV, raising=False)
    _arm(tmp_path)
    requested_sleeps = []

    async def forbidden_sleep(seconds):
        requested_sleeps.append(seconds)

    result = await maybe_delay_tr026_core_ingestion(
        _event(), state_dir=tmp_path, sleeper=forbidden_sleep
    )

    assert result.applied is False
    assert result.reason == "missing_case_token"
    assert requested_sleeps == []
    assert len(list((tmp_path / "local-qa" / "tr-026" / "armed").glob("*.json"))) == 1


@pytest.mark.asyncio
async def test_runtime_token_must_match_the_armed_plan_digest(monkeypatch, tmp_path):
    _set_runtime_contract(monkeypatch)
    _arm(tmp_path)
    wrong_token = base64.urlsafe_b64encode(b"x" * 32).decode().rstrip("=")
    monkeypatch.setenv(CASE_TOKEN_ENV, wrong_token)
    monkeypatch.setenv(
        SESSION_REF_ENV,
        "qa_" + hashlib.sha256(wrong_token.encode()).hexdigest()[:24],
    )

    wrong = await maybe_delay_tr026_core_ingestion(_event(), state_dir=tmp_path)

    assert wrong.applied is False
    assert wrong.reason == "case_token_mismatch"
    assert len(list((tmp_path / "local-qa" / "tr-026" / "armed").glob("*.json"))) == 1

    monkeypatch.setenv(CASE_TOKEN_ENV, CANONICAL_TOKEN)
    monkeypatch.setenv(SESSION_REF_ENV, CANONICAL_SESSION_REF)
    accepted = await maybe_delay_tr026_core_ingestion(
        _event(), state_dir=tmp_path, sleeper=lambda _seconds: asyncio.sleep(0)
    )
    assert accepted.applied is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("environment_name", "environment_value", "reason"),
    [
        (CASE_ID_ENV, "OTHER-CASE", "case_id_mismatch"),
        (SESSION_REF_ENV, "qa_" + "0" * 24, "session_ref_mismatch"),
    ],
)
async def test_case_or_session_mismatch_fails_before_atomic_claim(
    monkeypatch, tmp_path, environment_name, environment_value, reason
):
    _set_runtime_contract(monkeypatch)
    _arm(tmp_path)
    monkeypatch.setenv(environment_name, environment_value)

    result = await maybe_delay_tr026_core_ingestion(_event(), state_dir=tmp_path)

    control_root = tmp_path / "local-qa" / "tr-026"
    assert result.applied is False
    assert result.reason == reason
    assert len(list((control_root / "armed").glob("*.json"))) == 1
    assert list((control_root / "consumed").glob("*.json")) == []


@pytest.mark.asyncio
async def test_wrong_owner_fails_closed_before_atomic_claim(monkeypatch, tmp_path):
    _set_runtime_contract(monkeypatch)
    _arm(tmp_path)

    result = await maybe_delay_tr026_core_ingestion(
        _event(owner_user_id=OWNER_USER_ID + 1), state_dir=tmp_path
    )

    control_root = tmp_path / "local-qa" / "tr-026"
    assert result.applied is False
    assert result.reason == "cross_owner"
    assert list((control_root / "consumed").glob("*.json")) == []
    assert len(list((control_root / "rejected").glob("*.json"))) == 1


@pytest.mark.asyncio
async def test_exact_target_writes_redacted_owner_mutable_hash_chained_audit(
    monkeypatch, tmp_path
):
    _set_runtime_contract(monkeypatch)
    _arm(tmp_path)
    requested_sleeps = []
    boundary_actions = []
    import utils.tr026_local_qa as control_module

    real_audit = control_module._audit

    def recording_audit(*args, **kwargs):
        boundary_actions.append(f"audit:{kwargs['outcome']}")
        return real_audit(*args, **kwargs)

    monkeypatch.setattr(control_module, "_audit", recording_audit)

    async def exact_sleep(seconds):
        requested_sleeps.append(seconds)
        boundary_actions.append(f"sleep:{seconds:.3f}")

    result = await maybe_delay_tr026_core_ingestion(
        _event(), state_dir=tmp_path, sleeper=exact_sleep
    )

    assert TR026_DELAY_MS == 280
    assert requested_sleeps == [0.280]
    assert boundary_actions == [
        "audit:claimed",
        "audit:delay_requested",
        "sleep:0.280",
    ]
    assert result.applied is True
    assert result.delay_ms == 280
    evidence = _read_audit(tmp_path)
    assert [item["outcome"] for item in evidence] == ["claimed", "delay_requested"]
    serialized = json.dumps(evidence, sort_keys=True)
    assert CANONICAL_TOKEN not in serialized
    assert str(_event().chat_id) not in serialized
    audit_files = list((tmp_path / "local-qa" / "tr-026" / "audit").glob("*.json"))
    assert len(audit_files) == 2
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in audit_files)
    assert [item["chain_index"] for item in evidence] == [1, 2]
    assert evidence[0]["previous_record_hash"] == "0" * 64
    assert evidence[1]["previous_record_hash"] == evidence[0]["record_hash"]
    assert all(
        item["ledger_semantics"] == "owner_mutable_append_only_tamper_evident"
        for item in evidence
    )


@pytest.mark.asyncio
async def test_audit_hash_chain_rejects_owner_mutation(monkeypatch, tmp_path):
    _set_runtime_contract(monkeypatch)
    _arm(tmp_path)
    await maybe_delay_tr026_core_ingestion(
        _event(), state_dir=tmp_path, sleeper=lambda _seconds: asyncio.sleep(0)
    )
    audit_files = sorted((tmp_path / "local-qa" / "tr-026" / "audit").glob("*.json"))
    first = audit_files[0]
    record = json.loads(first.read_text(encoding="utf-8"))
    record["outcome"] = "altered"
    first.chmod(0o600)
    first.write_text(json.dumps(record), encoding="utf-8")
    first.chmod(0o600)

    with pytest.raises(ValueError, match="audit ledger integrity"):
        _read_audit(tmp_path)


@pytest.mark.asyncio
async def test_claim_is_atomic_one_shot_and_does_not_reapply_after_restart(
    monkeypatch, tmp_path
):
    _set_runtime_contract(monkeypatch)
    _arm(tmp_path)
    sleep_started = asyncio.Event()
    release_sleep = asyncio.Event()

    async def held_sleep(seconds):
        assert seconds == 0.280
        sleep_started.set()
        await release_sleep.wait()

    first = asyncio.create_task(
        maybe_delay_tr026_core_ingestion(
            _event(), state_dir=tmp_path, sleeper=held_sleep
        )
    )
    await sleep_started.wait()
    concurrent = await maybe_delay_tr026_core_ingestion(
        _event(), state_dir=tmp_path, sleeper=held_sleep
    )
    release_sleep.set()
    claimed = await first
    restarted_process = await maybe_delay_tr026_core_ingestion(
        _event(), state_dir=tmp_path, sleeper=held_sleep
    )

    assert claimed.applied is True
    assert concurrent.applied is False
    assert restarted_process.applied is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("override", "reason"),
    [
        ({"chat_id": -100_701}, "cross_chat"),
        ({"thread_id": 32}, "cross_thread"),
        ({"source_sequence": 7_003}, "cross_sequence"),
        ({"event_kind": "telegram_control"}, "wrong_event_kind"),
    ],
)
async def test_wrong_scope_fails_closed(monkeypatch, tmp_path, override, reason):
    _set_runtime_contract(monkeypatch)
    _arm(tmp_path)
    slept = False

    async def forbidden_sleep(_seconds):
        nonlocal slept
        slept = True

    result = await maybe_delay_tr026_core_ingestion(
        _event(**override), state_dir=tmp_path, sleeper=forbidden_sleep
    )

    assert result.applied is False
    assert result.reason == reason
    assert slept is False
    evidence = _read_audit(tmp_path)
    assert evidence[-1]["outcome"] == "rejected"
    assert evidence[-1]["reason"] == reason


@pytest.mark.asyncio
async def test_malformed_and_expired_plans_fail_closed(monkeypatch, tmp_path):
    _set_runtime_contract(monkeypatch)
    control_root = tmp_path / "local-qa" / "tr-026"
    _arm(tmp_path)
    armed_dir = control_root / "armed"
    next(armed_dir.glob("*.json")).write_text("{malformed", encoding="utf-8")

    malformed = await maybe_delay_tr026_core_ingestion(_event(), state_dir=tmp_path)
    assert malformed.applied is False
    assert malformed.reason == "malformed_plan"

    _arm(tmp_path)
    plan_path = next(armed_dir.glob("*.json"))
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["event"]["source_sequence"] = 7_002.5
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    plan_path.chmod(0o600)
    malformed_number = await maybe_delay_tr026_core_ingestion(
        _event(), state_dir=tmp_path
    )
    assert malformed_number.applied is False
    assert malformed_number.reason == "malformed_plan"

    _arm(tmp_path, ttl_seconds=1)
    plan_path = next(armed_dir.glob("*.json"))
    expires_at_ms = json.loads(plan_path.read_text(encoding="utf-8"))["expires_at_ms"]
    import utils.tr026_local_qa as control_module

    monkeypatch.setattr(control_module.time, "time", lambda: expires_at_ms / 1000 + 1)
    expired = await maybe_delay_tr026_core_ingestion(_event(), state_dir=tmp_path)
    assert expired.applied is False
    assert expired.reason == "expired"


@pytest.mark.asyncio
async def test_production_default_never_reads_or_applies_an_armed_plan(
    monkeypatch, tmp_path
):
    receipt = _arm(tmp_path)
    monkeypatch.delenv("VIVENTIUM_TELEGRAM_LOCAL_QA_MODE", raising=False)
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))

    result = await maybe_delay_tr026_core_ingestion(_event(), state_dir=tmp_path)

    after = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    assert result.applied is False
    assert result.reason == "disabled"
    assert before == after
    assert receipt.session_ref == CANONICAL_SESSION_REF


@pytest.mark.asyncio
async def test_normal_and_control_turns_have_no_effect_on_the_armed_target(
    monkeypatch, tmp_path
):
    _set_runtime_contract(monkeypatch)
    _arm(tmp_path)
    slept = []

    async def record_sleep(seconds):
        slept.append(seconds)

    normal = await maybe_delay_tr026_core_ingestion(
        _event(update_id=880_001, source_sequence=7_001),
        state_dir=tmp_path,
        sleeper=record_sleep,
    )
    control = await maybe_delay_tr026_core_ingestion(
        _event(update_id=880_003, source_sequence=7_003, event_kind="telegram_control"),
        state_dir=tmp_path,
        sleeper=record_sleep,
    )
    target = await maybe_delay_tr026_core_ingestion(
        _event(), state_dir=tmp_path, sleeper=record_sleep
    )

    assert normal.applied is False
    assert normal.reason == "not_targeted"
    assert control.applied is False
    assert control.reason == "not_targeted"
    assert target.applied is True
    assert slept == [0.280]


@pytest.mark.asyncio
async def test_cleanup_requires_the_case_token_and_never_removes_audit(
    monkeypatch, tmp_path
):
    _set_runtime_contract(monkeypatch)
    _arm(tmp_path)
    wrong_token = base64.urlsafe_b64encode(b"x" * 32).decode().rstrip("=")
    wrong_session_ref = "qa_" + hashlib.sha256(wrong_token.encode()).hexdigest()[:24]
    assert (
        cleanup_tr026_control(
            state_dir=tmp_path,
            case_id=CANONICAL_CASE_ID,
            case_token=wrong_token,
            session_ref=wrong_session_ref,
        )
        is False
    )
    assert (
        cleanup_tr026_control(
            state_dir=tmp_path,
            case_id=CANONICAL_CASE_ID,
            case_token=CANONICAL_TOKEN,
            session_ref=CANONICAL_SESSION_REF,
        )
        is True
    )

    result = await maybe_delay_tr026_core_ingestion(_event(), state_dir=tmp_path)

    assert result.applied is False
    assert result.reason == "not_targeted"
    evidence = _read_audit(tmp_path)
    assert evidence[-1]["outcome"] == "cleaned"


def test_consumed_artifact_survives_process_restart(monkeypatch, tmp_path):
    _arm(tmp_path)
    script = """
import asyncio, json, os
from dataclasses import asdict
from utils.tr026_local_qa import SyntheticTelegramSourceEvent, maybe_delay_tr026_core_ingestion
event = SyntheticTelegramSourceEvent(
    update_id=880002, chat_id=-100700, thread_id=31, source_sequence=7002,
    owner_user_id=12345
)
result = asyncio.run(maybe_delay_tr026_core_ingestion(event))
print(json.dumps(asdict(result), sort_keys=True))
"""
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(BOT_DIR)
    environment["VIVENTIUM_TELEGRAM_LOCAL_QA_MODE"] = "tr-026"
    environment[CASE_ID_ENV] = CANONICAL_CASE_ID
    environment[CASE_TOKEN_ENV] = CANONICAL_TOKEN
    environment[SESSION_REF_ENV] = CANONICAL_SESSION_REF
    environment["VIVENTIUM_TELEGRAM_STATE_DIR"] = str(tmp_path)

    first = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    restarted = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert json.loads(first.stdout)["applied"] is True
    assert json.loads(restarted.stdout) == {
        "applied": False,
        "artifact_ref": "",
        "delay_ms": 0,
        "reason": "not_targeted",
    }


def test_cli_arm_audit_and_token_cleanup_interface_is_stdin_only_and_redacted(tmp_path):
    command = [
        sys.executable,
        str(BOT_DIR / "utils" / "tr026_local_qa.py"),
        "--state-dir",
        str(tmp_path),
    ]
    arm_args = ["arm"]
    private_arm_envelope = json.dumps(
        {
            "schema_version": 1,
            "case_id": CANONICAL_CASE_ID,
            "case_token": CANONICAL_TOKEN,
            "session_ref": CANONICAL_SESSION_REF,
            "target": {
                "owner_user_id": OWNER_USER_ID,
                "chat_id": -100_700,
                "thread_id": 31,
                "stale_source_sequence": 7_001,
                "source_sequence": 7_002,
                "update_id": 880_002,
            },
            "ttl_seconds": 120,
        }
    )
    armed = subprocess.run(
        command + arm_args,
        check=True,
        capture_output=True,
        input=private_arm_envelope,
        text=True,
    )
    receipt = json.loads(armed.stdout)
    duplicate = subprocess.run(
        command + arm_args,
        check=False,
        capture_output=True,
        input=private_arm_envelope,
        text=True,
    )
    assert duplicate.returncode == 2
    assert "Traceback" not in duplicate.stderr
    assert str(BOT_DIR) not in duplicate.stderr
    assert str(tmp_path) not in duplicate.stderr
    assert json.loads(duplicate.stderr) == {
        "case_id": "TR-026",
        "error": "control_already_armed",
    }

    cleaned = subprocess.run(
        command
        + [
            "cleanup",
            "--case-id",
            CANONICAL_CASE_ID,
            "--session-ref",
            CANONICAL_SESSION_REF,
        ],
        check=True,
        capture_output=True,
        input=CANONICAL_TOKEN + "\n",
        text=True,
    )
    audit = subprocess.run(
        command
        + [
            "audit",
            "--case-id",
            CANONICAL_CASE_ID,
            "--session-ref",
            CANONICAL_SESSION_REF,
        ],
        check=True,
        capture_output=True,
        input=CANONICAL_TOKEN + "\n",
        text=True,
    )
    missing_token = subprocess.run(
        command
        + [
            "audit",
            "--case-id",
            CANONICAL_CASE_ID,
            "--session-ref",
            CANONICAL_SESSION_REF,
        ],
        check=False,
        capture_output=True,
        input="",
        text=True,
    )

    assert receipt == {
        "artifact_ref": hashlib.sha256(CANONICAL_TOKEN.encode()).hexdigest()[:16],
        "session_ref": CANONICAL_SESSION_REF,
    }
    assert json.loads(cleaned.stdout) == {
        "artifact_ref": receipt["artifact_ref"],
        "cleaned": True,
        "session_ref": CANONICAL_SESSION_REF,
    }
    assert json.loads(audit.stdout)["evidence"][-1]["outcome"] == "cleaned"
    all_process_output = (
        f"{armed.stdout}{armed.stderr}{duplicate.stdout}{duplicate.stderr}"
        f"{cleaned.stdout}{cleaned.stderr}{audit.stdout}{audit.stderr}"
    )
    assert CANONICAL_TOKEN not in all_process_output
    assert CANONICAL_TOKEN not in " ".join(armed.args)
    assert arm_args == ["arm"]
    assert not {
        "--case-id",
        "--session-ref",
        "--owner-user-id",
        "--chat-id",
        "--thread-id",
        "--stale-source-sequence",
        "--source-sequence",
        "--update-id",
    }.intersection(armed.args)
    assert CANONICAL_TOKEN not in " ".join(cleaned.args)
    assert CANONICAL_TOKEN not in " ".join(audit.args)
    assert missing_token.returncode == 2
    assert "Traceback" not in missing_token.stderr
    assert str(BOT_DIR) not in missing_token.stderr
    assert str(tmp_path) not in missing_token.stderr
    assert json.loads(missing_token.stderr) == {
        "case_id": "TR-026",
        "error": "case_token_required_on_stdin",
    }


@pytest.mark.parametrize(
    "private_input",
    [
        "",
        " " * 4_097,
        json.dumps(
            {
                "schema_version": 1,
                "case_id": CANONICAL_CASE_ID,
                "case_token": CANONICAL_TOKEN,
                "session_ref": CANONICAL_SESSION_REF,
                "target": {},
                "ttl_seconds": 120,
                "unexpected": True,
            }
        ),
        '{"schema_version":1,"schema_version":1}',
        "{}{}",
    ],
    ids=["missing", "oversized", "extra-field", "duplicate-field", "multiple-json"],
)
def test_cli_arm_rejects_missing_oversized_or_nonexact_private_envelopes(
    tmp_path, private_input
):
    command = [
        sys.executable,
        str(BOT_DIR / "utils" / "tr026_local_qa.py"),
        "--state-dir",
        str(tmp_path),
        "arm",
    ]

    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        input=private_input,
        text=True,
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert "Traceback" not in result.stderr
    assert str(BOT_DIR) not in result.stderr
    assert str(tmp_path) not in result.stderr
    assert CANONICAL_TOKEN not in result.stderr
    assert json.loads(result.stderr)["error"] in {
        "arm_envelope_required_on_stdin",
        "invalid_private_arm_envelope",
    }


def test_cli_arm_help_exposes_no_scope_arguments(tmp_path):
    command = [
        sys.executable,
        str(BOT_DIR / "utils" / "tr026_local_qa.py"),
        "--state-dir",
        str(tmp_path),
        "arm",
        "--help",
    ]

    result = subprocess.run(command, check=True, capture_output=True, text=True)

    assert result.stderr == ""
    assert not {
        "--case-id",
        "--session-ref",
        "--owner-user-id",
        "--chat-id",
        "--thread-id",
        "--stale-source-sequence",
        "--source-sequence",
        "--update-id",
    }.intersection(result.stdout.split())


def test_readme_arm_example_passes_private_scope_only_through_stdin():
    section = README.read_text(encoding="utf-8").split(
        "### TR-026 installed local-QA control", 1
    )[1]
    arm_example = section.split("```bash", 1)[1].split("```", 1)[0]

    assert 'tr026_local_qa.py arm < "$TR026_PRIVATE_ARM_ENVELOPE_FILE"' in arm_example
    assert not {
        "--case-id",
        "--session-ref",
        "--owner-user-id",
        "--chat-id",
        "--thread-id",
        "--stale-source-sequence",
        "--source-sequence",
        "--update-id",
    }.intersection(arm_example.split())

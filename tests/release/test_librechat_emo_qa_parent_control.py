from __future__ import annotations

import base64
import importlib.util
import json
import os
import stat
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from qa_control_test_support import write_artifact_identity

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "viventium" / "librechat_emo_qa_parent_control.py"
FIXTURE_SCRIPT = ROOT / "scripts" / "viventium" / "librechat_emo_qa_fixture.js"
SESSION_SCRIPT = ROOT / "scripts" / "viventium" / "local_qa_runtime_control.py"
CLI = ROOT / "bin" / "viventium"
NESTED_FAULT_SERVICE = (
    ROOT
    / "viventium_v0_4"
    / "LibreChat"
    / "api/server/services/viventium/LocalQaCortexFaultService.js"
)
NESTED_FAULT_CONTROL = (
    ROOT
    / "viventium_v0_4"
    / "LibreChat"
    / "scripts/viventium-cortex-fault-control.js"
)

BOUNDARIES = (
    "cortex_ledger_first_write",
    "web_replay_persistence",
    "web_redis_publish_ack",
    "telegram_promoted_parent_presentation",
)


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeRunner:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.controls: dict[str, dict[str, object]] = {}
        self.rows_present = False

    def __call__(self, **call):
        self.calls.append(call)
        argv = [str(part) for part in call["argv"]]
        document = call["document"]
        if argv[1].endswith("librechat_emo_qa_fixture.js"):
            action = argv[2]
            fixture = document["fixture"]
            hashes = {
                key: fixture[key]
                for key in (
                    "caseTokenHash",
                    "ownerScopeHash",
                    "conversationScopeHash",
                    "parentScopeHash",
                )
            }
            if action == "provision":
                self.rows_present = True
                rows = {"conversation": 1, "message": 1, "user": 1}
            elif action == "inspect":
                count = 1 if self.rows_present else 0
                rows = {"conversation": count, "message": count, "user": count}
            else:
                assert action == "destroy"
                self.rows_present = False
                rows = {"conversation": 0, "message": 0, "user": 0}
            return {
                "action": action,
                "caseId": "EMO-UC-048",
                "fixtureRef": document["fixtureRef"],
                "hashes": hashes,
                "rows": rows,
                "schemaVersion": 1,
            }

        action = argv[2]
        boundary = document.get("boundary")
        fixture = call["fixture"]
        if action == "arm":
            control = {
                "armedAt": "2026-08-23T12:00:02.000+00:00",
                "audit": [
                    {
                        "at": "2026-08-23T12:00:02.000+00:00",
                        "event": "armed",
                        "sequence": 1,
                    }
                ],
                "boundary": boundary,
                "controlId": f"emo048_{len(self.controls):032x}",
                "conversationScopeHash": fixture["conversationScopeHash"],
                "expiresAt": "2026-08-23T12:02:02.000+00:00",
                "ownerScopeHash": fixture["ownerScopeHash"],
                "parentScopeHash": fixture["parentScopeHash"],
                "purgeAt": "2026-08-24T12:02:02.000+00:00",
                "state": "armed",
                "syntheticScope": True,
            }
            self.controls[str(boundary)] = control
            return control
        if action == "query":
            values = list(self.controls.values())
            return [row for row in values if not boundary or row["boundary"] == boundary]
        assert action == "clear"
        keys = [
            key
            for key, value in self.controls.items()
            if (not boundary or key == boundary) and value["state"] == "armed"
        ]
        for key in keys:
            self.controls[key] = {
                **self.controls[key],
                "audit": [
                    *self.controls[key]["audit"],
                    {
                        "at": "2026-08-23T12:00:03.000+00:00",
                        "event": "cleared",
                        "sequence": 2,
                    },
                ],
                "clearedAt": "2026-08-23T12:00:03.000+00:00",
                "state": "cleared",
            }
        return {"cleared": len(keys)}


def _install_artifact_identity(installed: Path, identity: Path) -> None:
    write_artifact_identity(installed, identity)


def fixture(tmp_path: Path):
    session = load(SESSION_SCRIPT, "local_qa_runtime_control_emo_parent")
    installed = tmp_path / "installed"
    librechat = installed / "viventium_v0_4" / "LibreChat"
    (librechat / "scripts").mkdir(parents=True)
    (librechat / "scripts" / "viventium-cortex-fault-control.js").write_text(
        "// installed fixture\n", encoding="utf-8"
    )
    (librechat / "package.json").write_text("{}\n", encoding="utf-8")
    runtime = tmp_path / "runtime"
    state = runtime / "local-qa" / "active.json"
    emo_state = runtime / "local-qa" / "emo-uc-048.json"
    identity = runtime / "parallel-work-artifact-identity.json"
    request = runtime / "parallel-work-local-qa-request.json"
    runtime_env = runtime / "service-env" / "librechat.env"
    runtime_env.parent.mkdir(parents=True)
    _install_artifact_identity(installed, identity)
    request.write_text(
        '{"contractVersion":1,"mode":"local-qa","requested":true}\n', encoding="utf-8"
    )
    os.chmod(request, 0o600)
    runtime_env.write_text(
        "MONGO_URI=mongodb://127.0.0.1:27117/LibreChatQa\n", encoding="utf-8"
    )
    os.chmod(runtime_env, 0o600)
    now = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)
    redacted = session.activate_session(
        state_path=state,
        installed_root=installed,
        artifact_identity_path=identity,
        local_qa_request_path=request,
        case_id="EMO-UC-048",
        expires_in_seconds=900,
        now=now,
        token_bytes=lambda size: b"e" * size,
    )
    token = base64.urlsafe_b64encode(b"e" * 32).decode().rstrip("=")
    return {
        "artifact_identity_path": identity,
        "installed_root": installed,
        "local_qa_request_path": request,
        "now": now,
        "parent_state_path": emo_state,
        "runtime_env_path": runtime_env,
        "session": redacted,
        "session_state_path": state,
        "token": token,
    }


def prepare(module, values, runner):
    random_values = iter((bytes.fromhex("ab" * 12), bytes.fromhex("cd" * 16)))
    return module.prepare_fixture(
        **{
            key: value
            for key, value in values.items()
            if key.endswith("_path") or key == "installed_root"
        },
        now=values["now"] + timedelta(seconds=1),
        random_bytes=lambda size: next(random_values),
        runner=runner,
    )


def test_prepare_creates_exact_private_candidate_bound_fixture(tmp_path: Path) -> None:
    module = load(SCRIPT, "librechat_emo_qa_parent_control_prepare")
    values = fixture(tmp_path)
    runner = FakeRunner()

    result = prepare(module, values, runner)
    state = json.loads(values["parent_state_path"].read_text(encoding="utf-8"))
    call = runner.calls[0]
    private_document = call["document"]
    raw_scope = (
        state["ownerId"],
        state["conversationId"],
        state["parentMessageId"],
    )

    assert result == {
        "caseId": "EMO-UC-048",
        "expiresAt": "2026-08-23T12:15:00.000+00:00",
        "fixtureRef": state["fixtureRef"],
        "ownerScopeHash": state["ownerScopeHash"],
        "conversationScopeHash": state["conversationScopeHash"],
        "parentScopeHash": state["parentScopeHash"],
        "sessionRef": values["session"]["sessionRef"],
    }
    assert state["ownerId"] == "ab" * 12
    assert state["conversationId"] == "emo_uc_048_conversation_" + "cd" * 16
    assert state["parentMessageId"] == "emo_uc_048_parent_" + "cd" * 16
    assert private_document == {
        "fixture": {
            "caseTokenHash": state["caseTokenHash"],
            "componentArtifactDigest": state["componentArtifactDigest"],
            "conversationId": state["conversationId"],
            "conversationScopeHash": state["conversationScopeHash"],
            "email": "emo-uc-048-" + "cd" * 16 + "@local-qa.invalid",
            "expiresAt": state["expiresAt"],
            "ownerId": state["ownerId"],
            "ownerScopeHash": state["ownerScopeHash"],
            "parentMessageId": state["parentMessageId"],
            "parentScopeHash": state["parentScopeHash"],
        },
        "fixtureRef": state["fixtureRef"],
        "schemaVersion": 1,
    }
    assert stat.S_IMODE(values["parent_state_path"].stat().st_mode) == 0o600
    assert stat.S_IMODE(values["parent_state_path"].parent.stat().st_mode) == 0o700
    state_text = values["parent_state_path"].read_text(encoding="utf-8")
    assert values["token"] not in state_text
    assert values["token"] not in json.dumps(result)
    assert all(raw not in json.dumps(result) for raw in raw_scope)
    assert state["email"] not in json.dumps(result)
    assert "cd" * 16 not in json.dumps(result)
    assert all(raw not in "\0".join(call["argv"]) for raw in raw_scope)
    assert values["token"] not in "\0".join(call["argv"])
    assert call["env"].get("VIVENTIUM_LOCAL_QA_CASE_TOKEN") is None
    assert (
        call["env"]["VIVENTIUM_LOCAL_QA_COMPONENT_ARTIFACT_DIGEST"]
        == state["componentArtifactDigest"]
    )
    assert call["private_fd"] is True


def test_prepare_rejects_an_echoed_component_artifact_digest_in_fixture_receipt(
    tmp_path: Path,
) -> None:
    module = load(SCRIPT, "librechat_emo_qa_parent_control_digest_receipt")
    values = fixture(tmp_path)

    class EchoedComponentDigestRunner(FakeRunner):
        def __call__(self, **call):
            result = super().__call__(**call)
            argv = [str(part) for part in call["argv"]]
            if argv[1].endswith("librechat_emo_qa_fixture.js"):
                result = {
                    **result,
                    "hashes": {
                        **result["hashes"],
                        "componentArtifactDigest": call["document"]["fixture"][
                            "componentArtifactDigest"
                        ],
                    },
                }
            return result

    with pytest.raises(ValueError, match="operation_failed"):
        prepare(module, values, EchoedComponentDigestRunner())


@pytest.mark.parametrize("boundary", BOUNDARIES)
def test_each_boundary_arms_through_installed_cli_with_private_scope(
    tmp_path: Path, boundary: str
) -> None:
    module = load(SCRIPT, f"librechat_emo_qa_parent_control_{boundary}")
    values = fixture(tmp_path)
    runner = FakeRunner()
    prepare(module, values, runner)

    result = module.arm_fault(
        **{
            key: value
            for key, value in values.items()
            if key.endswith("_path") or key == "installed_root"
        },
        boundary=boundary,
        ttl_seconds=120,
        now=values["now"] + timedelta(seconds=2),
        runner=runner,
    )
    state = json.loads(values["parent_state_path"].read_text(encoding="utf-8"))
    call = runner.calls[-1]
    argv = "\0".join(call["argv"])

    assert result["boundary"] == boundary
    assert result["state"] == "armed"
    assert result["ownerScopeHash"] == state["ownerScopeHash"]
    assert call["document"] == {
        "boundary": boundary,
        "schemaVersion": 1,
        "scope": {
            "conversationId": state["conversationId"],
            "ownerId": state["ownerId"],
            "parentMessageId": state["parentMessageId"],
        },
        "ttlSeconds": 120,
    }
    assert call["env"]["VIVENTIUM_LOCAL_QA_CASE_TOKEN"] == values["token"]
    assert call["env"]["VIVENTIUM_LOCAL_QA_MODE"] == "emo_uc_048"
    assert (
        call["env"]["VIVENTIUM_LOCAL_QA_COMPONENT_ARTIFACT_DIGEST"]
        == state["componentArtifactDigest"]
    )
    assert call["private_fd"] is True
    assert values["token"] not in argv
    assert state["ownerId"] not in argv
    assert state["conversationId"] not in argv
    assert state["parentMessageId"] not in argv

    common = {
        key: value
        for key, value in values.items()
        if key.endswith("_path") or key == "installed_root"
    }
    queried = module.query_faults(**common, boundary=boundary, runner=runner)
    assert [row["controlId"] for row in queried["controls"]] == [result["controlId"]]
    assert module.clear_faults(**common, boundary=boundary, runner=runner)["cleared"] == 1
    after_clear = module.query_faults(**common, boundary=boundary, runner=runner)
    assert [row["state"] for row in after_clear["controls"]] == ["cleared"]


def test_arm_rejects_expiry_overrun_and_artifact_or_request_drift(tmp_path: Path) -> None:
    module = load(SCRIPT, "librechat_emo_qa_parent_control_arm_reject")
    values = fixture(tmp_path)
    runner = FakeRunner()
    prepare(module, values, runner)
    common = {
        key: value
        for key, value in values.items()
        if key.endswith("_path") or key == "installed_root"
    }

    with pytest.raises(ValueError, match="expiry"):
        module.arm_fault(
            **common,
            boundary=BOUNDARIES[0],
            ttl_seconds=120,
            now=values["now"] + timedelta(minutes=14),
            runner=runner,
        )

    values["artifact_identity_path"].write_text('{"candidate":"b"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="artifact identity"):
        module.arm_fault(
            **common,
            boundary=BOUNDARIES[0],
            ttl_seconds=30,
            now=values["now"] + timedelta(seconds=3),
            runner=runner,
        )


def test_query_clear_and_cleanup_are_restart_safe_and_survive_expiry_and_artifact_change(
    tmp_path: Path,
) -> None:
    module = load(SCRIPT, "librechat_emo_qa_parent_control_cleanup")
    values = fixture(tmp_path)
    runner = FakeRunner()
    prepare(module, values, runner)
    common = {
        key: value
        for key, value in values.items()
        if key.endswith("_path") or key == "installed_root"
    }
    for boundary in BOUNDARIES:
        module.arm_fault(
            **common,
            boundary=boundary,
            ttl_seconds=120,
            now=values["now"] + timedelta(seconds=2),
            runner=runner,
        )
    values["artifact_identity_path"].write_text('{"candidate":"replacement"}\n', encoding="utf-8")

    queried = module.query_faults(**common, boundary=None, runner=runner)
    assert len(queried["controls"]) == 4
    cleared = module.clear_faults(**common, boundary=None, runner=runner)
    assert cleared["cleared"] == 4
    result = module.cleanup_fixture(**common, runner=runner)

    assert result == {
        "caseId": "EMO-UC-048",
        "cleaned": True,
        "sessionRef": values["session"]["sessionRef"],
    }
    assert not values["parent_state_path"].exists()
    assert runner.rows_present is False
    assert module.cleanup_fixture(**common, runner=runner) == {
        "caseId": "EMO-UC-048",
        "cleaned": False,
        "sessionRef": values["session"]["sessionRef"],
    }


def test_cleanup_keeps_fixture_and_private_state_if_a_control_remains_armed(
    tmp_path: Path,
) -> None:
    module = load(SCRIPT, "librechat_emo_qa_parent_control_stuck_clear")
    values = fixture(tmp_path)

    class StuckClearRunner(FakeRunner):
        def __call__(self, **call):
            if call["argv"][2] == "clear":
                self.calls.append(call)
                return {"cleared": 0}
            return super().__call__(**call)

    runner = StuckClearRunner()
    prepare(module, values, runner)
    common = {
        key: value
        for key, value in values.items()
        if key.endswith("_path") or key == "installed_root"
    }
    module.arm_fault(
        **common,
        boundary=BOUNDARIES[0],
        ttl_seconds=120,
        now=values["now"] + timedelta(seconds=2),
        runner=runner,
    )

    with pytest.raises(ValueError, match="not clear"):
        module.cleanup_fixture(**common, runner=runner)
    assert values["parent_state_path"].exists()
    assert runner.rows_present is True


def test_parent_session_clear_is_blocked_until_fixture_and_controls_are_clean(
    tmp_path: Path,
) -> None:
    module = load(SCRIPT, "librechat_emo_qa_parent_control_clear_gate")
    values = fixture(tmp_path)
    runner = FakeRunner()
    common = {
        key: value
        for key, value in values.items()
        if key.endswith("_path") or key == "installed_root"
    }
    assert module.session_clearable(**common) == {
        "caseId": "EMO-UC-048",
        "clearable": True,
    }
    prepare(module, values, runner)
    assert module.session_clearable(**common) == {
        "caseId": "EMO-UC-048",
        "clearable": False,
    }


def test_cli_docs_and_central_qa_ownership_expose_the_root_hookup() -> None:
    cli = CLI.read_text(encoding="utf-8")
    owners = (ROOT / "qa" / "release-test-owners.yaml").read_text(encoding="utf-8")
    doc = (
        ROOT / "docs" / "requirements_and_learnings" / "55_Parallel_Work_Orchestration.md"
    ).read_text(encoding="utf-8")
    cases = (ROOT / "qa" / "emotional-cortex" / "cases.md").read_text(encoding="utf-8")

    for command in (
        "prepare-emo-insight",
        "arm-emo-insight",
        "query-emo-insight",
        "clear-emo-insight",
        "cleanup-emo-insight",
    ):
        assert command in cli
        assert command in doc
    assert "librechat_emo_qa_parent_control.py" in cli
    assert "test_librechat_emo_qa_parent_control.py" in owners
    assert "qa/emotional-cortex/cases.md" in owners
    assert "tests/release/test_librechat_emo_qa_parent_control.py" in cases
    assert "fresh random namespace" in cases
    assert "raw owner" in cases
    assert "NOT YET RUN" in cases


def test_fixture_helper_is_root_only_and_uses_installed_mongoose_schemas() -> None:
    source = FIXTURE_SCRIPT.read_text(encoding="utf-8")
    assert "createRequire" in source
    assert "@librechat/data-schemas" in source
    assert "createModels" in source
    assert "models.User" in source
    assert "models.Conversation" in source
    assert "models.Message" in source
    assert "LocalQaCortexFaultControl" in source
    assert "MONGO_URI" in source
    assert "/Users/" not in source
    assert "--scope-fd" in source
    assert "fstatSync" in source
    assert "readFileSync(0" not in source
    assert "inherited owner-only file descriptor" in source
    assert "stdin only" not in source


def test_no_raw_scope_or_token_options_exist_in_parent_cli() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    forbidden = (
        "--owner-id",
        "--conversation-id",
        "--parent-message-id",
        "--case-token",
        "--mongo-uri",
    )
    assert all(option not in source for option in forbidden)
    assert "capture_output=True" not in source
    assert "selectors.DefaultSelector" in source
    assert "operation_failed" in source
    assert "print(exc" not in source


def test_public_cli_whitelists_emo_arguments_before_parent_dispatch() -> None:
    source = CLI.read_text(encoding="utf-8")
    branch = source.rsplit("      prepare-emo-insight)", 1)[1].split(
        "      inject-release-claim|restore-release-claim)", 1
    )[0]

    assert "qa_emo_user_args=()" in branch
    assert '"${qa_emo_user_args[@]}"' in branch
    assert '"$@"' not in branch
    assert "--parent-state" not in branch
    assert "--session-state" not in branch
    assert "--installed-root" not in branch
    assert "--runtime-env" not in branch


def test_parent_cli_does_not_echo_rejected_private_arguments(capsys) -> None:
    module = load(SCRIPT, "librechat_emo_qa_parent_control_argparse_privacy")
    private_value = "private-" + os.urandom(12).hex()

    assert module.main(["prepare", "--case-token", private_value]) == 2
    captured = capsys.readouterr()
    assert private_value not in captured.out
    assert private_value not in captured.err
    assert captured.out == ""
    assert json.loads(captured.err) == {
        "caseId": "EMO-UC-048",
        "error": "operation_failed",
    }


def test_parent_cli_rejects_duplicate_options_without_echo(capsys) -> None:
    module = load(SCRIPT, "librechat_emo_qa_parent_control_duplicate_arg_privacy")
    private_value = "private-" + os.urandom(12).hex()

    assert module.main(
        [
            "prepare",
            "--parent-state",
            "/tmp/first",
            "--parent-state",
            private_value,
        ]
    ) == 2
    captured = capsys.readouterr()
    assert private_value not in captured.out
    assert private_value not in captured.err
    assert captured.out == ""
    assert json.loads(captured.err) == {
        "caseId": "EMO-UC-048",
        "error": "operation_failed",
    }


@pytest.mark.parametrize(
    ("field", "invalid"),
    (
        ("armedAt", "2026-08-23T12:00:02.000Z"),
        ("expiresAt", "2026-08-23T12:02:02+00:00"),
        ("purgeAt", "2026-08-24T12:02:02.0000+00:00"),
        ("audit", "2026-08-23T12:00:02.000Z"),
    ),
)
def test_control_receipt_requires_exact_iso_milliseconds(
    field: str, invalid: str
) -> None:
    module = load(SCRIPT, f"librechat_emo_timestamp_{field}")
    state = {
        "ownerScopeHash": "sha256:" + "1" * 64,
        "conversationScopeHash": "sha256:" + "2" * 64,
        "parentScopeHash": "sha256:" + "3" * 64,
    }
    row = {
        "armedAt": "2026-08-23T12:00:02.000+00:00",
        "audit": [
            {
                "at": "2026-08-23T12:00:02.000+00:00",
                "event": "armed",
                "sequence": 1,
            }
        ],
        "boundary": BOUNDARIES[0],
        "controlId": "emo048_" + "a" * 32,
        "conversationScopeHash": state["conversationScopeHash"],
        "expiresAt": "2026-08-23T12:02:02.000+00:00",
        "ownerScopeHash": state["ownerScopeHash"],
        "parentScopeHash": state["parentScopeHash"],
        "purgeAt": "2026-08-24T12:02:02.000+00:00",
        "state": "armed",
        "syntheticScope": True,
    }
    if field == "audit":
        row["audit"][0]["at"] = invalid
    else:
        row[field] = invalid

    with pytest.raises(ValueError, match="operation_failed"):
        module._validate_control_row(row, state, boundary=BOUNDARIES[0])


def test_private_runner_rejects_scope_in_argv_or_child_output(tmp_path: Path) -> None:
    module = load(SCRIPT, "librechat_emo_qa_parent_control_private_runner")
    private_value = "private-" + os.urandom(12).hex()
    environment = os.environ.copy()
    environment["PRIVATE_TEST_VALUE"] = private_value

    with pytest.raises(ValueError, match="operation_failed"):
        module._run_private_json(
            argv=[sys.executable, "-c", "print('{}')", private_value],
            cwd=tmp_path,
            env=environment,
            document={"schemaVersion": 1},
            private_values=[private_value],
        )

    with pytest.raises(ValueError, match="operation_failed"):
        module._run_private_json(
            argv=[
                sys.executable,
                "-c",
                "import os; print(os.environ['PRIVATE_TEST_VALUE'])",
            ],
            cwd=tmp_path,
            env=environment,
            document={"schemaVersion": 1},
            private_values=[private_value],
        )


def test_private_runner_can_supply_an_owner_only_inherited_fd(tmp_path: Path) -> None:
    module = load(SCRIPT, "librechat_emo_qa_parent_control_private_fd")
    probe = (
        "import json, os, stat, sys; "
        "fd=int(sys.argv[-1]); mode=stat.S_IMODE(os.fstat(fd).st_mode); "
        "doc=json.load(os.fdopen(fd)); "
        "print(json.dumps({'mode': mode, 'schemaVersion': doc['schemaVersion']}))"
    )

    assert module._run_private_json(
        argv=[sys.executable, "-c", probe],
        cwd=tmp_path,
        env=os.environ.copy(),
        document={"schemaVersion": 1},
        private_values=[],
        private_fd=True,
    ) == {"mode": 0o600, "schemaVersion": 1}


def test_private_runner_rejects_duplicate_keys_in_child_json(tmp_path: Path) -> None:
    module = load(SCRIPT, "librechat_emo_qa_parent_control_child_duplicates")

    with pytest.raises(ValueError, match="operation_failed"):
        module._run_private_json(
            argv=[
                sys.executable,
                "-c",
                'print(\'{"outer":{"value":1,"value":1}}\')',
            ],
            cwd=tmp_path,
            env=os.environ.copy(),
            document={"schemaVersion": 1},
            private_values=[],
        )

def test_fixture_helper_compare_and_deletes_every_exact_marker() -> None:
    source = FIXTURE_SCRIPT.read_text(encoding="utf-8")
    assert "userDeleteFilter" in source
    assert "conversationDeleteFilter" in source
    assert "messageDeleteFilter" in source
    assert "deleteOne({ _id: rows.owner._id })" not in source
    assert "deleteOne({ _id: rows.conversation._id })" not in source
    assert "deleteOne({ _id: rows.parent._id })" not in source


def test_prepare_is_idempotent_for_one_session_and_keeps_one_namespace(tmp_path: Path) -> None:
    module = load(SCRIPT, "librechat_emo_qa_parent_control_idempotent")
    values = fixture(tmp_path)
    runner = FakeRunner()
    first = prepare(module, values, runner)
    first_state = values["parent_state_path"].read_bytes()
    second = prepare(module, values, runner)
    second_state = values["parent_state_path"].read_bytes()

    assert first == second
    assert json.loads(first_state)["ownerId"] == json.loads(second_state)["ownerId"]
    assert len([call for call in runner.calls if call["argv"][2] == "provision"]) == 2


def test_arm_is_restart_safe_after_the_control_was_already_written(tmp_path: Path) -> None:
    module = load(SCRIPT, "librechat_emo_qa_parent_control_arm_restart")
    values = fixture(tmp_path)
    runner = FakeRunner()
    prepare(module, values, runner)
    common = {
        key: value
        for key, value in values.items()
        if key.endswith("_path") or key == "installed_root"
    }

    first = module.arm_fault(
        **common,
        boundary=BOUNDARIES[0],
        ttl_seconds=120,
        now=values["now"] + timedelta(seconds=2),
        runner=runner,
    )
    second = module.arm_fault(
        **common,
        boundary=BOUNDARIES[0],
        ttl_seconds=120,
        now=values["now"] + timedelta(seconds=3),
        runner=runner,
    )

    assert second == first
    assert len([call for call in runner.calls if call["argv"][2] == "arm"]) == 1


def test_query_rejects_duplicate_control_ids(tmp_path: Path) -> None:
    module = load(SCRIPT, "librechat_emo_qa_parent_control_duplicate_controls")
    values = fixture(tmp_path)

    class DuplicateControlRunner(FakeRunner):
        def __call__(self, **call):
            result = super().__call__(**call)
            if call["argv"][2] == "query" and result:
                return [result[0], dict(result[0])]
            return result

    runner = DuplicateControlRunner()
    prepare(module, values, runner)
    common = {
        key: value
        for key, value in values.items()
        if key.endswith("_path") or key == "installed_root"
    }
    module.arm_fault(
        **common,
        boundary=BOUNDARIES[0],
        ttl_seconds=120,
        now=values["now"] + timedelta(seconds=2),
        runner=runner,
    )

    with pytest.raises(ValueError, match="operation_failed"):
        module.query_faults(**common, boundary=BOUNDARIES[0], runner=runner)


def test_parent_state_duplicate_keys_and_expiry_drift_fail_closed(tmp_path: Path) -> None:
    module = load(SCRIPT, "librechat_emo_qa_parent_control_state_adversarial")
    values = fixture(tmp_path)
    runner = FakeRunner()
    prepare(module, values, runner)
    common = {
        key: value
        for key, value in values.items()
        if key.endswith("_path") or key == "installed_root"
    }

    raw_state = values["parent_state_path"].read_text(encoding="utf-8")
    values["parent_state_path"].write_text(
        raw_state.replace(
            '  "caseId": "EMO-UC-048",',
            '  "caseId": "EMO-UC-048",\n  "caseId": "EMO-UC-048",',
            1,
        ),
        encoding="utf-8",
    )
    os.chmod(values["parent_state_path"], 0o600)
    with pytest.raises(ValueError, match="fixture state is invalid"):
        module.query_faults(**common, boundary=None, runner=runner)

    values["parent_state_path"].write_text(raw_state, encoding="utf-8")
    os.chmod(values["parent_state_path"], 0o600)
    state = json.loads(raw_state)
    state["expiresAt"] = "2026-08-23T12:14:59.000+00:00"
    values["parent_state_path"].write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.chmod(values["parent_state_path"], 0o600)
    with pytest.raises(ValueError, match="different session"):
        module.query_faults(**common, boundary=None, runner=runner)


def test_remote_or_open_runtime_mongo_config_fails_closed(tmp_path: Path) -> None:
    module = load(SCRIPT, "librechat_emo_qa_parent_control_mongo")
    values = fixture(tmp_path)
    runner = FakeRunner()
    values["runtime_env_path"].write_text(
        "MONGO_URI=mongodb://remote.invalid:27017/qa\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="local"):
        prepare(module, values, runner)

    values["runtime_env_path"].write_text(
        "MONGO_URI=mongodb://127.0.0.1:27117/qa\n", encoding="utf-8"
    )
    os.chmod(values["runtime_env_path"], 0o644)
    with pytest.raises(ValueError, match="unavailable"):
        prepare(module, values, runner)


def test_duplicate_mongo_uri_fails_closed_without_last_wins(tmp_path: Path) -> None:
    module = load(SCRIPT, "librechat_emo_qa_parent_control_mongo_duplicate")
    values = fixture(tmp_path)
    values["runtime_env_path"].write_text(
        "MONGO_URI=mongodb://127.0.0.1:27117/first\n"
        "MONGO_URI=mongodb://127.0.0.1:27117/second\n",
        encoding="utf-8",
    )
    os.chmod(values["runtime_env_path"], 0o600)

    with pytest.raises(ValueError, match="invalid"):
        module._local_mongo_uri(values["runtime_env_path"])


@pytest.mark.parametrize(
    "mongo_uri",
    (
        "mongodb://user:secret@127.0.0.1:27117/qa",
        "mongodb://127.0.0.1:27117/qa?replicaSet=qa",
        "mongodb://127.0.0.1:27117/qa#fragment",
        "mongodb://127.0.0.1:27117,localhost:27118/qa",
        "mongodb://LOCALHOST:27117/qa",
        "mongodb://localhost.:27117/qa",
        "mongodb://127.0.0.1/qa",
        "mongodb://127.0.0.1:27117/qa/extra",
    ),
)
def test_mongo_uri_requires_one_exact_loopback_seed(
    tmp_path: Path, mongo_uri: str
) -> None:
    module = load(SCRIPT, "librechat_emo_qa_parent_control_mongo_adversarial")
    values = fixture(tmp_path)
    values["runtime_env_path"].write_text(
        f"MONGO_URI={mongo_uri}\n", encoding="utf-8"
    )
    os.chmod(values["runtime_env_path"], 0o600)

    with pytest.raises(ValueError, match="local"):
        module._local_mongo_uri(values["runtime_env_path"])


@pytest.mark.parametrize(
    "mongo_uri",
    (
        "mongodb://127.0.0.1:27117/qa",
        "mongodb://localhost:27017/LibreChatQa",
        "mongodb://[::1]:27018/qa-db",
    ),
)
def test_mongo_uri_accepts_one_exact_loopback_seed(
    tmp_path: Path, mongo_uri: str
) -> None:
    module = load(SCRIPT, "librechat_emo_qa_parent_control_mongo_local")
    values = fixture(tmp_path)
    values["runtime_env_path"].write_text(
        f"MONGO_URI={mongo_uri}\n", encoding="utf-8"
    )
    os.chmod(values["runtime_env_path"], 0o600)

    assert module._local_mongo_uri(values["runtime_env_path"]) == mongo_uri


def test_root_fixture_contract_matches_nested_component_digest_authority() -> None:
    nested = NESTED_FAULT_SERVICE.read_text(encoding="utf-8")
    parent = SCRIPT.read_text(encoding="utf-8")
    fixture_source = FIXTURE_SCRIPT.read_text(encoding="utf-8")

    assert (
        "VIVENTIUM_LOCAL_QA_COMPONENT_ARTIFACT_DIGEST" in nested
        and "VIVENTIUM_LOCAL_QA_COMPONENT_ARTIFACT_DIGEST" in parent
    )
    assert "'componentArtifactDigest'" in nested
    assert "parent?.metadata?.viventium?.localQaFixture" in nested
    assert "marker.componentArtifactDigest === componentArtifactDigest" in nested
    assert "componentArtifactDigest" in fixture_source
    assert "artifactIdentityDigest" not in fixture_source


def test_nested_control_emits_canonical_iso_milliseconds() -> None:
    module = load(SCRIPT, "librechat_emo_qa_parent_control_nested_timestamp")
    probe = r"""
const Module = require('module');
const originalLoad = Module._load;
const row = {
  schemaVersion: 1,
  controlId: 'emo048_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
  caseTokenHash: `sha256:${'1'.repeat(64)}`,
  boundary: 'cortex_ledger_first_write',
  ownerScopeHash: `sha256:${'2'.repeat(64)}`,
  conversationScopeHash: `sha256:${'3'.repeat(64)}`,
  parentScopeHash: `sha256:${'4'.repeat(64)}`,
  syntheticScope: true,
  state: 'armed',
  armedAt: new Date('2026-08-23T12:00:02.123Z'),
  expiresAt: new Date('2026-08-23T12:02:02.456Z'),
  purgeAt: new Date('2026-08-24T12:02:02.789Z'),
  consumedAt: new Date('2026-08-23T12:01:02.111Z'),
  clearedAt: new Date('2026-08-23T12:01:03.222Z'),
  audit: [{ sequence: 1, event: 'armed', at: new Date('2026-08-23T12:00:02.123Z') }],
};
Module._load = function (request, parent, isMain) {
  if (request === '@librechat/api') {
    return {
      createCortexLocalQaFaultControlManager: ({ store }) => ({
        arm: async () => store.insert(row),
        query: async () => [],
        clear: async () => 0,
        consume: async () => ({ triggered: false }),
      }),
    };
  }
  return originalLoad.call(this, request, parent, isMain);
};
const control = require(process.argv[1]);
const privateModels = {
  LocalQaCortexFaultIssuance: { create: async (value) => value },
  LocalQaCortexFaultTerminalReceipt: {
    collection: { replaceOne: async () => ({ acknowledged: true }) },
  },
};
const service = control.createLocalQaCortexFaultService({
  ControlModel: {
    db: { model: (name) => privateModels[name] },
    create: async (value) => ({
      ...value,
      consumedAt: row.consumedAt,
      clearedAt: row.clearedAt,
    }),
  },
  UserModel: {},
  ConversationModel: {},
  MessageModel: {},
  env: {},
});
service.arm({}).then((value) => process.stdout.write(JSON.stringify(value)));
"""
    completed = subprocess.run(
        [module._node_binary(), "-e", probe, str(NESTED_FAULT_SERVICE)],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    emitted = json.loads(completed.stdout)

    assert emitted["armedAt"] == "2026-08-23T12:00:02.123+00:00"
    assert emitted["expiresAt"] == "2026-08-23T12:02:02.456+00:00"
    assert emitted["purgeAt"] == "2026-08-24T12:02:02.789+00:00"
    assert emitted["consumedAt"] == "2026-08-23T12:01:02.111+00:00"
    assert emitted["clearedAt"] == "2026-08-23T12:01:03.222+00:00"
    assert emitted["audit"][0]["at"] == "2026-08-23T12:00:02.123+00:00"


def _run_nested_scope_cli(
    *,
    node: str,
    descriptor: int,
    extra_args: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            node,
            str(NESTED_FAULT_CONTROL),
            "query",
            "--scope-fd",
            str(descriptor),
            *(extra_args or []),
        ],
        check=False,
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin"},
        pass_fds=(descriptor,),
        timeout=10,
    )


@pytest.mark.parametrize(
    ("payload", "extra_args", "expected_error"),
    (
        (
            b'{"schemaVersion":1,"schemaVersion":1,"scope":{"ownerId":"owner","conversationId":"conversation","parentMessageId":"parent"}}',
            [],
            "fault_control_scope_document_invalid",
        ),
        (
            b'{"schemaVersion":1,"scope":{"ownerId":"owner","ownerId":"owner","conversationId":"conversation","parentMessageId":"parent"}}',
            [],
            "fault_control_scope_document_invalid",
        ),
        (
            b'{"schemaVersion":1,"scope":{"ownerId":"owner-\xff","conversationId":"conversation","parentMessageId":"parent"}}',
            [],
            "fault_control_scope_document_invalid",
        ),
        (
            b'{"schemaVersion":1,"scope":{"ownerId":"owner","conversationId":"conversation","parentMessageId":"parent"}}'
            + b" " * 8192,
            [],
            "fault_control_scope_document_invalid",
        ),
        (
            b'{"schemaVersion":1,"scope":{"ownerId":"owner","conversationId":"conversation","parentMessageId":"parent"}}',
            ["--json", "--json"],
            "fault_control_arguments_invalid",
        ),
        (
            b'{"schemaVersion":1,"scope":{"ownerId":"owner","conversationId":"conversation","parentMessageId":"parent"}}',
            ["--unknown"],
            "fault_control_arguments_invalid",
        ),
    ),
)
def test_nested_scope_cli_strict_reader_rejects_ambiguous_input(
    tmp_path: Path,
    payload: bytes,
    extra_args: list[str],
    expected_error: str,
) -> None:
    module = load(SCRIPT, f"librechat_emo_nested_reader_{expected_error}_{len(payload)}")
    scope_path = tmp_path / "scope.json"
    scope_path.write_bytes(payload)
    scope_path.chmod(0o600)
    descriptor = os.open(scope_path, os.O_RDONLY)
    try:
        completed = _run_nested_scope_cli(
            node=module._node_binary(),
            descriptor=descriptor,
            extra_args=extra_args,
        )
    finally:
        os.close(descriptor)

    assert completed.returncode == 1
    assert completed.stdout == ""
    assert json.loads(completed.stderr) == {"ok": False, "error": expected_error}


def test_nested_scope_cli_rejects_duplicate_scope_fd(tmp_path: Path) -> None:
    module = load(SCRIPT, "librechat_emo_nested_reader_duplicate_fd")
    scope_path = tmp_path / "scope.json"
    scope_path.write_text(
        '{"schemaVersion":1,"scope":{"ownerId":"owner","conversationId":"conversation","parentMessageId":"parent"}}',
        encoding="utf-8",
    )
    scope_path.chmod(0o600)
    descriptor = os.open(scope_path, os.O_RDONLY)
    try:
        completed = _run_nested_scope_cli(
            node=module._node_binary(),
            descriptor=descriptor,
            extra_args=["--scope-fd", str(descriptor)],
        )
    finally:
        os.close(descriptor)

    assert completed.returncode == 1
    assert completed.stdout == ""
    assert json.loads(completed.stderr) == {
        "ok": False,
        "error": "fault_control_arguments_invalid",
    }


def test_nested_scope_cli_rejects_non_private_descriptor(tmp_path: Path) -> None:
    module = load(SCRIPT, "librechat_emo_nested_reader_public_file")
    scope_path = tmp_path / "scope.json"
    scope_path.write_text(
        '{"schemaVersion":1,"scope":{"ownerId":"owner","conversationId":"conversation","parentMessageId":"parent"}}',
        encoding="utf-8",
    )
    scope_path.chmod(0o644)
    descriptor = os.open(scope_path, os.O_RDONLY)
    try:
        completed = _run_nested_scope_cli(
            node=module._node_binary(), descriptor=descriptor
        )
    finally:
        os.close(descriptor)

    assert completed.returncode == 1
    assert completed.stdout == ""
    assert json.loads(completed.stderr) == {
        "ok": False,
        "error": "fault_control_scope_channel_not_private",
    }


def test_nested_scope_cli_rejects_non_regular_descriptor() -> None:
    module = load(SCRIPT, "librechat_emo_nested_reader_pipe")
    read_descriptor, write_descriptor = os.pipe()
    try:
        os.write(
            write_descriptor,
            b'{"schemaVersion":1,"scope":{"ownerId":"owner","conversationId":"conversation","parentMessageId":"parent"}}',
        )
        os.close(write_descriptor)
        write_descriptor = -1
        completed = _run_nested_scope_cli(
            node=module._node_binary(), descriptor=read_descriptor
        )
    finally:
        os.close(read_descriptor)
        if write_descriptor >= 0:
            os.close(write_descriptor)

    assert completed.returncode == 1
    assert completed.stdout == ""
    assert json.loads(completed.stderr) == {
        "ok": False,
        "error": "fault_control_scope_channel_invalid",
    }

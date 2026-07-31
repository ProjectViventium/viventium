from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER_PATH = REPO_ROOT / "scripts" / "viventium" / "telegram_poller_handoff.py"
LAUNCHER_PATH = REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh"


def load_helper():
    spec = importlib.util.spec_from_file_location("telegram_poller_handoff", HELPER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def extract_shell_function(text: str, name: str) -> str:
    lines = text.splitlines()
    start = next(
        index for index, line in enumerate(lines) if line.strip() == f"{name}() {{"
    )
    depth = 0
    collected: list[str] = []
    for line in lines[start:]:
        collected.append(line)
        depth += line.count("{")
        depth -= line.count("}")
        if depth == 0:
            break
    return "\n".join(collected) + "\n"


class FakeInspector:
    def __init__(self, processes):
        self.processes = dict(processes)

    def inspect(self, pid):
        return self.processes.get(int(pid))


def process(helper, *, pid=4312, start_id="boot-a:99", cwd="/opt/viventium/viventium_v0_4/telegram-viventium/TelegramVivBot"):
    return helper.ProcessIdentity(
        pid=pid,
        uid=os.getuid(),
        start_id=start_id,
        command="/opt/python bot.py",
        cwd=cwd,
    )


def write_secure_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(json.dumps(payload), encoding="utf-8")
    path.chmod(0o600)


def owner_payload(
    helper,
    proc,
    *,
    token="123456:secret",
    repo_root="/opt/viventium",
    execution_root=None,
    launch_script="/state/launches/old/start.sh",
    readiness_proof="polling_started",
    schema_version=1,
):
    payload = {
        "schema_version": schema_version,
        "kind": helper.OWNER_KIND,
        "token_sha256": helper.token_sha256(token),
        "pid": proc.pid,
        "process_start_id": proc.start_id,
        "repo_root": repo_root,
        "working_directory": proc.cwd,
        "launch_script": launch_script,
        "ready": True,
        "readiness_proof": readiness_proof,
    }
    if execution_root is not None:
        payload["execution_root"] = str(execution_root)
    return payload


def test_owner_receipt_contains_hash_but_never_token(tmp_path: Path) -> None:
    helper = load_helper()
    token = "123456:super-secret-value"
    proc = process(helper)
    receipt = tmp_path / "owner.json"

    helper.write_owner_receipt(
        receipt,
        token=token,
        process=proc,
        repo_root=Path("/opt/viventium"),
        launch_script=tmp_path / "launches" / "current" / "start.sh",
        ready=False,
    )

    text = receipt.read_text(encoding="utf-8")
    payload = json.loads(text)
    assert token not in text
    assert "super-secret-value" not in text
    assert payload["token_sha256"] == helper.token_sha256(token)
    assert payload["ready"] is False
    assert receipt.stat().st_mode & 0o777 == 0o600


def test_owner_receipt_tracks_source_provenance_separately_from_execution_root(
    tmp_path: Path,
) -> None:
    helper = load_helper()
    token = "123456:super-secret-value"
    source_repo = tmp_path / "source"
    execution_root = (
        tmp_path
        / "Application Support"
        / "Viventium"
        / "runtime-components"
        / "telegram-viventium"
        / "code"
        / ("a" * 64)
        / "viventium_v0_4"
        / "telegram-viventium"
        / "TelegramVivBot"
    )
    proc = process(helper, cwd=str(execution_root))
    receipt = tmp_path / "owner.json"

    helper.write_owner_receipt(
        receipt,
        token=token,
        process=proc,
        repo_root=source_repo,
        execution_root=execution_root,
        launch_script=tmp_path / "launches" / "current" / "start.sh",
        ready=True,
        readiness_proof="polling_started",
    )

    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 2
    assert payload["repo_root"] == str(source_repo.resolve())
    assert payload["execution_root"] == str(execution_root.resolve())
    assert helper.load_recognized_owner(
        receipt,
        token_hash=helper.token_sha256(token),
        inspector=FakeInspector({proc.pid: proc}),
    ) == payload


def test_schema_two_owner_rejects_source_checkout_process_when_execution_is_installed(
    tmp_path: Path,
) -> None:
    helper = load_helper()
    token = "123456:secret"
    source_repo = tmp_path / "source"
    execution_root = tmp_path / "Application Support" / "runtime-component"
    source_process = process(
        helper,
        cwd=str(
            source_repo
            / "viventium_v0_4"
            / "telegram-viventium"
            / "TelegramVivBot"
        ),
    )
    receipt = tmp_path / "owner.json"
    write_secure_json(
        receipt,
        owner_payload(
            helper,
            source_process,
            token=token,
            repo_root=str(source_repo),
            execution_root=str(execution_root),
            schema_version=2,
        ),
    )

    assert helper.load_recognized_owner(
        receipt,
        token_hash=helper.token_sha256(token),
        inspector=FakeInspector({source_process.pid: source_process}),
    ) is None


def test_schema_two_owner_without_execution_root_fails_closed(
    tmp_path: Path,
) -> None:
    helper = load_helper()
    token = "123456:secret"
    source_repo = tmp_path / "source"
    source_process = process(
        helper,
        cwd=str(
            source_repo
            / "viventium_v0_4"
            / "telegram-viventium"
            / "TelegramVivBot"
        ),
    )
    receipt = tmp_path / "owner.json"
    write_secure_json(
        receipt,
        owner_payload(
            helper,
            source_process,
            token=token,
            repo_root=str(source_repo),
            schema_version=2,
        ),
    )

    assert helper.load_recognized_owner(
        receipt,
        token_hash=helper.token_sha256(token),
        inspector=FakeInspector({source_process.pid: source_process}),
    ) is None
    with pytest.raises(helper.HandoffError, match="execution_root"):
        helper._payload_execution_root(json.loads(receipt.read_text(encoding="utf-8")))


def test_recognized_owner_rejects_pid_reuse(tmp_path: Path) -> None:
    helper = load_helper()
    token = "123456:secret"
    original = process(helper, start_id="boot-a:99")
    reused = process(helper, start_id="boot-a:100")
    receipt = tmp_path / "owner.json"
    write_secure_json(receipt, owner_payload(helper, original, token=token))

    assert (
        helper.load_recognized_owner(
            receipt,
            token_hash=helper.token_sha256(token),
            inspector=FakeInspector({original.pid: reused}),
        )
        is None
    )


def test_recognized_owner_rejects_unknown_process_without_signalling(tmp_path: Path) -> None:
    helper = load_helper()
    token = "123456:secret"
    original = process(helper)
    unknown = helper.ProcessIdentity(
        pid=original.pid,
        uid=os.getuid(),
        start_id=original.start_id,
        command="/usr/bin/python unrelated.py",
        cwd="/tmp",
    )
    receipt = tmp_path / "owner.json"
    write_secure_json(receipt, owner_payload(helper, original, token=token))
    signals = []

    owner = helper.load_recognized_owner(
        receipt,
        token_hash=helper.token_sha256(token),
        inspector=FakeInspector({original.pid: unknown}),
    )
    assert owner is None
    assert helper.terminate_recognized_owner(
        owner,
        inspector=FakeInspector({original.pid: unknown}),
        signal_process=lambda pid, sig: signals.append((pid, sig)),
    ) is False
    assert signals == []


def test_upgrade_health_requires_ready_receipt_not_only_legacy_pid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    helper = load_helper()
    proc = process(helper)
    pid_file = tmp_path / "telegram_bot.pid"
    pid_file.write_text(f"{proc.pid}\n", encoding="utf-8")
    monkeypatch.setattr(
        helper,
        "SystemProcessInspector",
        lambda: FakeInspector({proc.pid: proc}),
    )

    assert helper._health(tmp_path / "state", pid_file)["running"] is True
    assert helper._health(
        tmp_path / "state",
        pid_file,
        require_receipt=True,
    ) == {"running": False, "ready": False}


def test_unsafe_receipt_cannot_downgrade_to_legacy_pid_trust(
    tmp_path: Path,
) -> None:
    helper = load_helper()
    token = "123456:secret"
    proc = process(helper)
    state_dir = tmp_path / "state"
    receipt = state_dir / f"owner-{helper.token_sha256(token)[:24]}.json"
    write_secure_json(receipt, owner_payload(helper, proc, token=token))
    receipt.chmod(0o644)
    pid_file = tmp_path / "telegram.pid"
    pid_file.write_text(f"{proc.pid}\n", encoding="utf-8")

    with pytest.raises(helper.HandoffError, match="permissions"):
        helper._status(
            state_dir=state_dir,
            token_hash=helper.token_sha256(token),
            pid_file=pid_file,
            legacy_launch_script=tmp_path / "legacy.sh",
            inspector=FakeInspector({proc.pid: proc}),
        )


def test_termination_rechecks_identity_before_signal(tmp_path: Path) -> None:
    helper = load_helper()
    token = "123456:secret"
    original = process(helper)
    receipt = tmp_path / "owner.json"
    write_secure_json(receipt, owner_payload(helper, original, token=token))
    first_inspector = FakeInspector({original.pid: original})
    owner = helper.load_recognized_owner(
        receipt,
        token_hash=helper.token_sha256(token),
        inspector=first_inspector,
    )
    assert owner is not None

    reused = process(helper, start_id="boot-a:100")
    signals = []
    assert helper.terminate_recognized_owner(
        owner,
        inspector=FakeInspector({original.pid: reused}),
        signal_process=lambda pid, sig: signals.append((pid, sig)),
    ) is False
    assert signals == []


def test_real_recognized_process_is_terminated_without_pattern_matching(
    tmp_path: Path,
) -> None:
    helper = load_helper()
    token = "123456:synthetic"
    repo_root = tmp_path / "checkout"
    cwd = (
        repo_root
        / "viventium_v0_4"
        / "telegram-viventium"
        / "TelegramVivBot"
    )
    cwd.mkdir(parents=True)
    bot_script = cwd / "bot.py"
    bot_script.write_text("import time\nwhile True: time.sleep(1)\n", encoding="utf-8")
    child = subprocess.Popen(
        [sys.executable, "bot.py"],
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        inspector = helper.SystemProcessInspector()
        current = None
        for _ in range(50):
            current = inspector.inspect(child.pid)
            if current and "bot.py" in current.command:
                break
            import time

            time.sleep(0.02)
        assert current is not None
        receipt = tmp_path / "state" / "owner.json"
        write_secure_json(
            receipt,
            owner_payload(
                helper,
                current,
                token=token,
                repo_root=str(repo_root),
                launch_script=str(tmp_path / "state" / "launches" / "start.sh"),
            ),
        )
        owner = helper.load_recognized_owner(
            receipt,
            token_hash=helper.token_sha256(token),
            inspector=inspector,
        )
        assert owner is not None
        assert helper.terminate_recognized_owner(
            owner, inspector=inspector, wait_timeout=3.0
        )
        child.wait(timeout=3)
    finally:
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=3)


def test_interrupted_handoff_restores_only_recognized_predecessor(tmp_path: Path) -> None:
    helper = load_helper()
    token = "123456:secret"
    predecessor = process(
        helper,
        pid=4312,
        cwd=str(tmp_path / "old" / "viventium_v0_4" / "telegram-viventium" / "TelegramVivBot"),
    )
    candidate = process(
        helper,
        pid=5312,
        start_id="boot-a:101",
        cwd=str(tmp_path / "new" / "viventium_v0_4" / "telegram-viventium" / "TelegramVivBot"),
    )
    state_dir = tmp_path / "state"
    launch_script = state_dir / "launches" / "old" / "start.sh"
    launch_script.parent.mkdir(parents=True, mode=0o700)
    launch_script.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
    launch_script.chmod(0o700)
    transaction = state_dir / "transactions" / "tx.json"
    payload = {
        "schema_version": 1,
        "kind": helper.TRANSACTION_KIND,
        "token_sha256": helper.token_sha256(token),
        "candidate": {
            "repo_root": str(tmp_path / "new"),
            "receipt_file": str(state_dir / "owner.json"),
        },
        "predecessor": owner_payload(
            helper,
            predecessor,
            token=token,
            repo_root=str(tmp_path / "old"),
            launch_script=str(launch_script),
        ),
    }
    write_secure_json(transaction, payload)
    launched = []

    result = helper.rollback_transaction(
        transaction,
        state_dir=state_dir,
        inspector=FakeInspector({candidate.pid: candidate}),
        launch_predecessor=lambda predecessor_payload: launched.append(predecessor_payload) or 6312,
        signal_process=lambda _pid, _sig: None,
    )

    assert result["restored"] is True
    assert launched and launched[0]["repo_root"] == str(tmp_path / "old")
    assert not transaction.exists()


def test_rollback_stops_attached_candidate_before_restoring_predecessor(
    tmp_path: Path,
) -> None:
    helper = load_helper()
    token = "123456:secret"
    state_dir = tmp_path / "state"
    candidate = process(
        helper,
        pid=5312,
        start_id="boot-a:101",
        cwd=str(tmp_path / "new" / "viventium_v0_4" / "telegram-viventium" / "TelegramVivBot"),
    )
    predecessor = process(
        helper,
        pid=4312,
        cwd=str(tmp_path / "old" / "viventium_v0_4" / "telegram-viventium" / "TelegramVivBot"),
    )
    launch_script = state_dir / "launches" / "old" / "start.sh"
    launch_script.parent.mkdir(parents=True, mode=0o700)
    launch_script.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
    launch_script.chmod(0o700)
    transaction = state_dir / "transactions" / "tx.json"
    candidate_process = {
        "pid": candidate.pid,
        "process_start_id": candidate.start_id,
        "repo_root": str(tmp_path / "new"),
        "working_directory": candidate.cwd,
    }
    write_secure_json(
        transaction,
        {
            "schema_version": 1,
            "kind": helper.TRANSACTION_KIND,
            "token_sha256": helper.token_sha256(token),
            "candidate": {
                "repo_root": str(tmp_path / "new"),
                "receipt_file": str(state_dir / "owner.json"),
                "process": candidate_process,
            },
            "predecessor": owner_payload(
                helper,
                predecessor,
                token=token,
                repo_root=str(tmp_path / "old"),
                launch_script=str(launch_script),
            ),
        },
    )
    inspector = FakeInspector({candidate.pid: candidate})
    signals = []

    result = helper.rollback_transaction(
        transaction,
        state_dir=state_dir,
        inspector=inspector,
        launch_predecessor=lambda _payload: 6312,
        signal_process=lambda pid, sig: (
            signals.append((pid, sig)),
            inspector.processes.pop(pid, None),
        ),
    )

    assert result["restored"] is True
    assert [pid for pid, _sig in signals] == [candidate.pid]


def test_rollback_rejects_tampered_predecessor_launch_path(tmp_path: Path) -> None:
    helper = load_helper()
    token = "123456:secret"
    predecessor = process(helper)
    state_dir = tmp_path / "state"
    transaction = state_dir / "transactions" / "tx.json"
    payload = {
        "schema_version": 1,
        "kind": helper.TRANSACTION_KIND,
        "token_sha256": helper.token_sha256(token),
        "candidate": {"repo_root": "/new", "receipt_file": str(state_dir / "owner.json")},
        "predecessor": owner_payload(
            helper,
            predecessor,
            token=token,
            launch_script="/tmp/untrusted-start.sh",
        ),
    }
    write_secure_json(transaction, payload)
    launched = []

    with pytest.raises(helper.HandoffError, match="trusted state directory"):
        helper.rollback_transaction(
            transaction,
            state_dir=state_dir,
            inspector=FakeInspector({}),
            launch_predecessor=lambda predecessor_payload: launched.append(predecessor_payload) or 1,
            signal_process=lambda _pid, _sig: None,
        )
    assert launched == []


def test_rollback_rejects_content_tampering_of_bound_predecessor_launcher(
    tmp_path: Path,
) -> None:
    helper = load_helper()
    token = "123456:secret"
    predecessor = process(helper)
    state_dir = tmp_path / "state"
    launch_script = state_dir / "transactions" / "rollback-launch.sh"
    launch_script.parent.mkdir(parents=True, mode=0o700)
    launch_script.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
    launch_script.chmod(0o700)
    launcher_sha256 = helper._file_sha256(launch_script)
    transaction = state_dir / "transactions" / "tx.json"
    predecessor_payload = owner_payload(
        helper,
        predecessor,
        token=token,
        launch_script=str(launch_script),
        schema_version=2,
        execution_root=tmp_path / "old",
    )
    predecessor_payload["launch_script_sha256"] = launcher_sha256
    write_secure_json(
        transaction,
        {
            "schema_version": 2,
            "kind": helper.TRANSACTION_KIND,
            "token_sha256": helper.token_sha256(token),
            "candidate": {
                "repo_root": "/new",
                "execution_root": str(tmp_path / "new"),
                "receipt_file": str(state_dir / "owner.json"),
            },
            "predecessor": predecessor_payload,
        },
    )
    launch_script.write_text("#!/bin/bash\nexit 99\n", encoding="utf-8")
    launch_script.chmod(0o700)

    with pytest.raises(helper.HandoffError, match="content hash"):
        helper.rollback_transaction(
            transaction,
            state_dir=state_dir,
            inspector=FakeInspector({}),
            launch_predecessor=lambda _payload: 1,
            signal_process=lambda _pid, _sig: None,
        )


@pytest.mark.parametrize(
    "tampered_name",
    ["telegram_bot_runtime.env", "telegram_overlay.env"],
)
def test_bound_rollback_package_rejects_sourced_environment_tampering(
    tmp_path: Path,
    tampered_name: str,
) -> None:
    helper = load_helper()
    state_dir = tmp_path / "state"
    source_dir = state_dir / "launches" / "source-attempt"
    source_dir.mkdir(parents=True, mode=0o700)
    launcher = source_dir / "telegram_bot_launch.sh"
    launcher.write_text(
        "#!/bin/bash\n# viventium-launch-package-schema: 1\nexit 0\n",
        encoding="utf-8",
    )
    launcher.chmod(0o700)
    for name in ("telegram_bot_runtime.env", "telegram_overlay.env"):
        artifact = source_dir / name
        artifact.write_text(f"export FIXTURE={name!r}\n", encoding="utf-8")
        artifact.chmod(0o600)
    snapshot_dir = state_dir / "transactions" / "tx.rollback-package"
    snapshot, launcher_sha256, package_sha256 = helper._snapshot_launch_package(
        launcher,
        snapshot_dir,
        state_dir=state_dir,
    )
    assert package_sha256 is not None
    (snapshot_dir / tampered_name).write_text(
        "export FIXTURE='tampered'\n",
        encoding="utf-8",
    )
    (snapshot_dir / tampered_name).chmod(0o600)

    with pytest.raises(helper.HandoffError, match="package content hash"):
        helper._trusted_bound_launch_script(
            str(snapshot),
            state_dir,
            expected_sha256=launcher_sha256,
            package_sha256=package_sha256,
        )


def test_generated_launch_package_cleanup_removes_only_exact_owned_package(
    tmp_path: Path,
) -> None:
    helper = load_helper()
    state_dir = tmp_path / "state"
    package_dir = state_dir / "launches" / "attempt"
    package_dir.mkdir(parents=True, mode=0o700)
    launcher = package_dir / "telegram_bot_launch.sh"
    launcher.write_text(
        "#!/bin/bash\n# viventium-launch-package-schema: 1\nexit 0\n",
        encoding="utf-8",
    )
    launcher.chmod(0o700)
    for name in ("telegram_bot_runtime.env", "telegram_overlay.env"):
        artifact = package_dir / name
        artifact.write_text("", encoding="utf-8")
        artifact.chmod(0o600)

    helper._cleanup_generated_launch_package(
        str(launcher),
        state_dir=state_dir,
    )

    assert not package_dir.exists()


def test_native_predecessor_cannot_downgrade_to_legacy_grace_on_rollback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    helper = load_helper()
    token = "123456:secret"
    state_dir = tmp_path / "state"
    execution_root = tmp_path / "old"
    working_directory = (
        execution_root
        / "viventium_v0_4"
        / "telegram-viventium"
        / "TelegramVivBot"
    )
    working_directory.mkdir(parents=True)
    launch_script = state_dir / "launches" / "old" / "start.sh"
    launch_script.parent.mkdir(parents=True, mode=0o700)
    launch_script.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
    launch_script.chmod(0o700)
    restored = process(
        helper,
        pid=6312,
        start_id="boot-a:restored",
        cwd=str(working_directory),
    )
    transaction = state_dir / "transactions" / "tx.json"
    write_secure_json(
        transaction,
        {
            "schema_version": 1,
            "kind": helper.TRANSACTION_KIND,
            "token_sha256": helper.token_sha256(token),
            "candidate": {
                "repo_root": str(tmp_path / "new"),
                "receipt_file": str(state_dir / "owner.json"),
            },
            "predecessor": owner_payload(
                helper,
                process(helper, cwd=str(working_directory)),
                token=token,
                repo_root=str(execution_root),
                launch_script=str(launch_script),
                readiness_proof="polling_started",
            ),
        },
    )
    clock = [0.0]

    def advance_clock() -> float:
        clock[0] += 9.0
        return clock[0]

    monkeypatch.setattr(helper.time, "monotonic", advance_clock)
    monkeypatch.setattr(helper.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        helper,
        "_default_launch_predecessor",
        lambda _payload, *, state_dir: restored.pid,
    )
    inspector = FakeInspector({restored.pid: restored})

    with pytest.raises(helper.HandoffError, match="native readiness"):
        helper.rollback_transaction(
            transaction,
            state_dir=state_dir,
            inspector=inspector,
            signal_process=lambda pid, _sig: inspector.processes.pop(pid, None),
        )
    assert transaction.exists()
    owner_receipt = state_dir / f"owner-{helper.token_sha256(token)[:24]}.json"
    assert not owner_receipt.exists()


def test_prepare_refuses_a_second_active_handoff(tmp_path: Path) -> None:
    helper = load_helper()
    state_dir = tmp_path / "state"
    transaction = state_dir / "transactions" / "handoff-active.json"
    write_secure_json(
        transaction,
        {
            "schema_version": 1,
            "kind": helper.TRANSACTION_KIND,
            "token_sha256": helper.token_sha256("123456:secret"),
        },
    )
    args = SimpleNamespace(
        state_dir=str(state_dir),
        pid_file=str(tmp_path / "telegram.pid"),
        legacy_launch_script=str(tmp_path / "legacy.sh"),
        candidate_repo=str(tmp_path / "new"),
        candidate_launch_script=str(tmp_path / "candidate.sh"),
        takeover=True,
        guard_timeout=30.0,
    )

    with pytest.raises(helper.HandoffError, match="already in progress"):
        helper._prepare(args, "123456:secret")


def test_guard_does_not_commit_premature_pre_poll_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    helper = load_helper()
    token = "123456:secret"
    state_dir = tmp_path / "state"
    transaction = state_dir / "transactions" / "handoff-active.json"
    candidate = process(
        helper,
        pid=5312,
        start_id="boot-a:101",
        cwd=str(
            tmp_path
            / "new"
            / "viventium_v0_4"
            / "telegram-viventium"
            / "TelegramVivBot"
        ),
    )
    receipt = state_dir / f"owner-{helper.token_sha256(token)[:24]}.json"
    write_secure_json(
        receipt,
        owner_payload(
            helper,
            candidate,
            token=token,
            repo_root=str(tmp_path / "new"),
            readiness_proof="initializing",
        ),
    )
    write_secure_json(
        transaction,
        {
            "schema_version": 1,
            "kind": helper.TRANSACTION_KIND,
            "token_sha256": helper.token_sha256(token),
            "candidate": {
                "repo_root": str((tmp_path / "new").resolve()),
                "receipt_file": str(receipt),
            },
            "predecessor": owner_payload(
                helper,
                process(helper, pid=4312),
                token=token,
            ),
        },
    )
    rolled_back: list[Path] = []
    monkeypatch.setattr(
        helper,
        "SystemProcessInspector",
        lambda: FakeInspector({candidate.pid: candidate}),
    )
    monkeypatch.setattr(
        helper,
        "rollback_transaction",
        lambda transaction_path, *, state_dir: rolled_back.append(transaction_path),
    )

    helper._guard(transaction, state_dir, timeout=0.01)

    assert rolled_back == [transaction]
    assert transaction.exists()


@pytest.mark.parametrize("success_edge_state", ["exit", "reused"])
def test_guard_revalidates_exact_attached_candidate_before_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    success_edge_state: str,
) -> None:
    helper = load_helper()
    token = "123456:secret"
    state_dir = tmp_path / "state"
    transaction = state_dir / "transactions" / "handoff-active.json"
    candidate_repo = tmp_path / "new"
    candidate = process(
        helper,
        pid=5312,
        start_id="boot-a:101",
        cwd=str(
            candidate_repo
            / "viventium_v0_4"
            / "telegram-viventium"
            / "TelegramVivBot"
        ),
    )
    receipt = state_dir / f"owner-{helper.token_sha256(token)[:24]}.json"
    write_secure_json(
        receipt,
        owner_payload(
            helper,
            candidate,
            token=token,
            repo_root=str(candidate_repo),
            readiness_proof="polling_started",
        ),
    )
    write_secure_json(
        transaction,
        {
            "schema_version": 1,
            "kind": helper.TRANSACTION_KIND,
            "token_sha256": helper.token_sha256(token),
            "candidate": {
                "repo_root": str(candidate_repo.resolve()),
                "receipt_file": str(receipt),
                "process": {
                    "pid": candidate.pid,
                    "process_start_id": candidate.start_id,
                    "repo_root": str(candidate_repo.resolve()),
                    "working_directory": candidate.cwd,
                },
            },
            "predecessor": owner_payload(
                helper,
                process(helper, pid=4312),
                token=token,
            ),
        },
    )

    class SuccessEdgeExitInspector:
        def __init__(self) -> None:
            self.calls = 0

        def inspect(self, pid):
            assert int(pid) == candidate.pid
            self.calls += 1
            if self.calls == 1:
                return candidate
            if success_edge_state == "reused":
                return process(
                    helper,
                    pid=candidate.pid,
                    start_id="boot-a:reused",
                    cwd=candidate.cwd,
                )
            return None

    rolled_back: list[Path] = []
    inspector = SuccessEdgeExitInspector()
    monkeypatch.setattr(helper, "SystemProcessInspector", lambda: inspector)
    monkeypatch.setattr(
        helper,
        "rollback_transaction",
        lambda transaction_path, *, state_dir: rolled_back.append(transaction_path),
    )

    helper._guard(transaction, state_dir, timeout=0.01)

    assert inspector.calls >= 2
    assert rolled_back == [transaction]
    assert transaction.exists()


def test_launcher_uses_stable_receipts_and_transactional_handoff() -> None:
    launcher = LAUNCHER_PATH.read_text(encoding="utf-8")
    start = launcher[
        launcher.index("start_telegram_bot() {") :
        launcher.index("\nschedule_deferred_telegram_bot_start() {")
    ]

    assert "telegram_poller_handoff.py" in launcher
    assert 'TELEGRAM_POLLER_STATE_DIR="${VIVENTIUM_TELEGRAM_POLLER_STATE_DIR:-$VIVENTIUM_STATE_ROOT/telegram-poller}"' in launcher
    assert "VIVENTIUM_TELEGRAM_OWNER_RECEIPT" in start
    assert "telegram_handoff_args=(" in start
    assert "    prepare" in start
    assert " wait-ready" in start
    assert " rollback" in start
    assert " commit" in start
    assert 'kill_by_pattern_scoped "python.*bot.py" "$PWD"' not in start
    assert 'local telegram_attach_timeout="${VIVENTIUM_TELEGRAM_HANDOFF_ATTACH_TIMEOUT_S:-8}"' in start
    assert 'local telegram_ready_timeout="${VIVENTIUM_TELEGRAM_HANDOFF_READY_TIMEOUT_S:-75}"' in start
    assert 'printf "%s\\n%s" "$VIVENTIUM_CORE_DIR" "$PWD"' in start
    assert "secrets.token_hex(8)" in start
    assert 'launches/${telegram_repo_launch_id}-${telegram_launch_attempt_id}' in start
    assert "# viventium-launch-package-schema: 1" in start
    assert 'source "\\$telegram_launch_package_dir/telegram_bot_runtime.env"' in start
    assert 'source "\\$telegram_launch_package_dir/telegram_overlay.env"' in start
    assert "cleanup_current_telegram_launch_package" in start
    assert "telegram_launchctl_eligible" in start
    assert "preserving that explicit location and using direct detached startup" in start
    assert "normalize_telegram_handoff_timeouts" in start
    assert '--guard-timeout "$telegram_guard_timeout"' in start
    assert '--candidate-pid "$TELEGRAM_BOT_PID"' in start
    assert '--transaction "$telegram_handoff_transaction"' in start
    assert '--candidate-execution-root "$PWD"' in start


def test_installed_candidate_transaction_matches_execution_root_not_source_repo(
    tmp_path: Path,
) -> None:
    helper = load_helper()
    token = "123456:synthetic"
    source_repo = tmp_path / "source"
    execution_root = (
        tmp_path
        / "Application Support"
        / "Viventium"
        / "runtime-components"
        / "telegram-viventium"
        / "code"
        / ("b" * 64)
        / "viventium_v0_4"
        / "telegram-viventium"
        / "TelegramVivBot"
    )
    execution_root.mkdir(parents=True)
    candidate = process(
        helper,
        pid=8123,
        start_id="boot-a:8123",
        cwd=str(execution_root),
    )
    receipt = tmp_path / "state" / f"owner-{helper.token_sha256(token)[:24]}.json"
    write_secure_json(
        receipt,
        owner_payload(
            helper,
            candidate,
            token=token,
            repo_root=str(source_repo),
            execution_root=str(execution_root),
            schema_version=2,
        ),
    )
    transaction = tmp_path / "state" / "transactions" / "handoff.json"
    write_secure_json(
        transaction,
        {
            "schema_version": 2,
            "kind": helper.TRANSACTION_KIND,
            "token_sha256": helper.token_sha256(token),
            "candidate": {
                "repo_root": str(source_repo.resolve()),
                "execution_root": str(execution_root.resolve()),
                "receipt_file": str(receipt),
                "process": {
                    "pid": candidate.pid,
                    "process_start_id": candidate.start_id,
                    "repo_root": str(source_repo.resolve()),
                    "execution_root": str(execution_root.resolve()),
                    "working_directory": candidate.cwd,
                },
            },
        },
    )

    recognized = helper._transaction_candidate_ready(
        json.loads(transaction.read_text(encoding="utf-8")),
        inspector=FakeInspector({candidate.pid: candidate}),
    )
    assert recognized is not None
    assert recognized["execution_root"] == str(execution_root.resolve())

    tampered = json.loads(transaction.read_text(encoding="utf-8"))
    tampered["candidate"]["process"]["execution_root"] = str(source_repo.resolve())
    assert (
        helper._transaction_candidate_ready(
            tampered,
            inspector=FakeInspector({candidate.pid: candidate}),
        )
        is None
    )


@pytest.mark.parametrize(
    ("attach", "ready", "guard", "expected"),
    [
        ("08", "09", "", "8 9 32"),
        ("999999999999999999999", "999999999999999999999", "", "8 75 98"),
        ("8", "75", "1", "8 75 98"),
        ("12", "120", "200", "12 120 200"),
    ],
)
def test_telegram_handoff_timeouts_are_bounded_base_ten(
    attach: str,
    ready: str,
    guard: str,
    expected: str,
) -> None:
    launcher = LAUNCHER_PATH.read_text(encoding="utf-8")
    normalize_function = extract_shell_function(
        launcher,
        "normalize_telegram_handoff_timeouts",
    )
    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                f"PYTHON_BIN={sys.executable!r}\n"
                f"{normalize_function}"
                f"normalize_telegram_handoff_timeouts {attach!r} {ready!r} {guard!r}\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert completed.stdout.strip() == expected


def test_wait_ready_fails_immediately_when_attached_candidate_exits(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    helper = load_helper()
    candidate_repo = tmp_path / "candidate"
    candidate_cwd = (
        candidate_repo
        / "viventium_v0_4"
        / "telegram-viventium"
        / "TelegramVivBot"
    )
    candidate_cwd.mkdir(parents=True)
    candidate = process(
        helper,
        pid=8123,
        start_id="boot-a:8123",
        cwd=str(candidate_cwd),
    )

    class ExitingInspector:
        def __init__(self) -> None:
            self.calls = 0

        def inspect(self, pid):
            assert int(pid) == candidate.pid
            self.calls += 1
            return candidate if self.calls == 1 else None

    inspector = ExitingInspector()
    monkeypatch.setattr(helper, "SystemProcessInspector", lambda: inspector)

    with pytest.raises(
        helper.HandoffError,
        match="exited before publishing readiness",
    ):
        helper._wait_ready(
            state_dir=tmp_path / "state",
            token_hash=helper.token_sha256("123456:synthetic"),
            candidate_repo=candidate_repo,
            candidate_pid=candidate.pid,
            timeout=30,
        )

    assert inspector.calls == 2


@pytest.mark.parametrize(
    ("success_edge_state", "error_match"),
    [
        ("exit", "exited before publishing readiness"),
        ("reused", "changed identity before publishing readiness"),
    ],
)
def test_wait_ready_revalidates_ready_owner_at_success_edge(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    success_edge_state: str,
    error_match: str,
) -> None:
    helper = load_helper()
    token = "123456:synthetic"
    candidate_repo = tmp_path / "candidate"
    candidate_cwd = (
        candidate_repo
        / "viventium_v0_4"
        / "telegram-viventium"
        / "TelegramVivBot"
    )
    candidate_cwd.mkdir(parents=True)
    candidate = process(
        helper,
        pid=8123,
        start_id="boot-a:8123",
        cwd=str(candidate_cwd),
    )
    receipt = tmp_path / "state" / f"owner-{helper.token_sha256(token)[:24]}.json"
    write_secure_json(
        receipt,
        owner_payload(
            helper,
            candidate,
            token=token,
            repo_root=str(candidate_repo),
            readiness_proof="polling_started",
        ),
    )

    class SuccessEdgeExitInspector:
        def __init__(self) -> None:
            self.calls = 0

        def inspect(self, pid):
            assert int(pid) == candidate.pid
            self.calls += 1
            if self.calls <= 2:
                return candidate
            if success_edge_state == "reused":
                return process(
                    helper,
                    pid=candidate.pid,
                    start_id="boot-a:reused",
                    cwd=candidate.cwd,
                )
            return None

    inspector = SuccessEdgeExitInspector()
    monkeypatch.setattr(helper, "SystemProcessInspector", lambda: inspector)

    with pytest.raises(
        helper.HandoffError,
        match=error_match,
    ):
        helper._wait_ready(
            state_dir=tmp_path / "state",
            token_hash=helper.token_sha256(token),
            candidate_repo=candidate_repo,
            candidate_pid=candidate.pid,
            timeout=30,
        )

    assert inspector.calls == 3


def test_commit_keeps_rollback_when_ready_candidate_exits_at_success_edge(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    helper = load_helper()
    token = "123456:synthetic"
    state_dir = tmp_path / "state"
    candidate_repo = tmp_path / "candidate"
    candidate = process(
        helper,
        pid=8123,
        start_id="boot-a:8123",
        cwd=str(
            candidate_repo
            / "viventium_v0_4"
            / "telegram-viventium"
            / "TelegramVivBot"
        ),
    )
    receipt = state_dir / f"owner-{helper.token_sha256(token)[:24]}.json"
    transaction = state_dir / "transactions" / "handoff-active.json"
    write_secure_json(
        receipt,
        owner_payload(
            helper,
            candidate,
            token=token,
            repo_root=str(candidate_repo),
            readiness_proof="polling_started",
        ),
    )
    write_secure_json(
        transaction,
        {
            "schema_version": 1,
            "kind": helper.TRANSACTION_KIND,
            "token_sha256": helper.token_sha256(token),
            "candidate": {
                "repo_root": str(candidate_repo.resolve()),
                "receipt_file": str(receipt),
                "process": {
                    "pid": candidate.pid,
                    "process_start_id": candidate.start_id,
                    "repo_root": str(candidate_repo.resolve()),
                    "working_directory": candidate.cwd,
                },
            },
            "predecessor": owner_payload(
                helper,
                process(helper, pid=4312),
                token=token,
            ),
        },
    )

    class SuccessEdgeExitInspector:
        def __init__(self) -> None:
            self.calls = 0

        def inspect(self, pid):
            assert int(pid) == candidate.pid
            self.calls += 1
            return candidate if self.calls == 1 else None

    inspector = SuccessEdgeExitInspector()
    monkeypatch.setattr(helper, "SystemProcessInspector", lambda: inspector)

    with pytest.raises(
        helper.HandoffError,
        match="not ready at commit",
    ):
        helper._commit(transaction)

    assert inspector.calls == 2
    assert transaction.exists()

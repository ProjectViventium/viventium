from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "viventium" / "local_qa_service_ack.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("local_qa_service_ack", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _wait_until_ready(check, *, timeout_seconds: float = 5.0):
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            value = check()
        except (OSError, RuntimeError, ValueError) as error:
            last_error = error
        else:
            if value:
                return value
        time.sleep(0.01)
    raise AssertionError("test process did not reach its expected live identity") from last_error


def _process_argv_contains(module, pid: int, *expected: str) -> bool:
    _image, argv = module._kernel_process_image_and_argv(pid)
    return all(value in argv for value in expected)


def _state(case_id: str = "PWK-UC-016") -> dict[str, object]:
    started = datetime(2026, 8, 25, 0, 0, tzinfo=timezone.utc)
    return {
        "artifactIdentityDigest": "sha256:" + "a" * 64,
        "caseId": case_id,
        "caseToken": base64.urlsafe_b64encode(b"k" * 32).decode().rstrip("="),
        "componentArtifactDigest": "sha256:" + "b" * 64,
        "contractVersion": 1,
        "expiresAt": (started + timedelta(minutes=15)).isoformat(
            timespec="milliseconds"
        ),
        "installedRootHash": "sha256:" + "c" * 64,
        "mode": "pwk_uc_016",
        "modeVariable": "VIVENTIUM_GLASSHIVE_LOCAL_QA_MODE",
        "sessionRef": "qa_test_session_12345678",
        "startedAt": started.isoformat(timespec="milliseconds"),
    }


def _process(pid: int, executable: Path, *, marker: str | None = None):
    return {
        "pid": pid,
        "startedAt": "2026-08-25T00:00:01.000+00:00",
        "startMarker": marker
        or "sha256:" + hashlib.sha256(str(pid).encode("utf-8")).hexdigest(),
        "executablePath": str(executable.resolve()),
        "executableSha256": "sha256:" + "e" * 64,
    }


@pytest.fixture
def module():
    return _load_module()


@pytest.fixture
def service_processes(tmp_path, module, monkeypatch):
    installed = tmp_path / "installed"
    monkeypatch.setattr(module, "INSTALLED_ROOT", installed, raising=False)
    core_root = installed / "viventium_v0_4" / "LibreChat"
    core_entrypoint = core_root / "api" / "server" / "index.js"
    telegram_root = (
        installed / "viventium_v0_4" / "telegram-viventium" / "TelegramVivBot"
    )
    telegram_entrypoint = telegram_root / "bot.py"
    glasshive_root = installed / "viventium_v0_4" / "GlassHive" / "runtime_phase1"
    glasshive_entrypoint = glasshive_root / ".venv" / "bin" / "uvicorn"
    glasshive_api = glasshive_root / "src" / "workers_projects_runtime" / "api.py"

    for entrypoint in (
        core_entrypoint,
        telegram_entrypoint,
        glasshive_entrypoint,
        glasshive_api,
    ):
        entrypoint.parent.mkdir(parents=True, exist_ok=True)

    core_entrypoint.write_text("setInterval(() => {}, 1000);\n", encoding="utf-8")
    telegram_entrypoint.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
    glasshive_entrypoint.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
    glasshive_entrypoint.chmod(0o755)
    glasshive_api.write_text("def create_app():\n    return None\n", encoding="utf-8")

    node = shutil.which("node")
    assert node is not None
    specifications = {
        "glasshive-runtime": {
            "argv": [
                sys.executable,
                str(glasshive_entrypoint),
                "workers_projects_runtime.api:create_app",
                "--factory",
            ],
            "cwd": glasshive_root,
            "executable": Path(sys.executable),
        },
        "librechat-core": {
            "argv": [node, "api/server/index.js"],
            "cwd": core_root,
            "executable": Path(node),
        },
        "telegram-bot": {
            "argv": [sys.executable, "bot.py"],
            "cwd": telegram_root,
            "executable": Path(sys.executable),
        },
    }
    processes = {}
    try:
        for service_id, specification in specifications.items():
            child = subprocess.Popen(
                specification["argv"],
                cwd=specification["cwd"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            processes[service_id] = {
                "child": child,
                "executable": specification["executable"],
                "installed": installed,
                "pid": child.pid,
            }
        assert len({process["pid"] for process in processes.values()}) == 3
        for service_id, process in processes.items():
            _wait_until_ready(
                lambda service_id=service_id, process=process: module._service_process_identity_valid(
                    service_id,
                    process["pid"],
                    process["executable"],
                )
            )
        yield processes
    finally:
        for process in processes.values():
            child = process["child"]
            child.terminate()
            child.wait(timeout=5)


def test_required_service_matrix_is_exact(module):
    assert module.REQUIRED_SERVICES == {
        "TR-026": ("librechat-core", "telegram-bot"),
        "EMO-UC-047": ("glasshive-runtime", "librechat-core"),
        "EMO-UC-048": ("librechat-core", "telegram-bot"),
        "MPV-061": ("librechat-core",),
        "PWK-UC-015": ("glasshive-runtime", "librechat-core", "telegram-bot"),
        "PWK-UC-016": ("glasshive-runtime", "librechat-core", "telegram-bot"),
        "PWK-UC-017": ("glasshive-runtime", "librechat-core", "telegram-bot"),
        "REL-UC-004": ("librechat-core",),
    }


def test_acknowledgement_is_private_signed_and_contains_no_token(
    module, tmp_path, service_processes
):
    payload = _state()
    ack_root = tmp_path / "acks"
    core = service_processes["librechat-core"]

    result = module.acknowledge(
        state_payload=payload,
        ack_root=ack_root,
        service_id="librechat-core",
        pid=core["pid"],
        parent_pid=core["pid"],
        executable_path=core["executable"],
        process_probe=lambda pid, path: _process(pid, path),
        now=datetime(2026, 8, 25, 0, 0, 2, tzinfo=timezone.utc),
    )

    ack_path = ack_root / str(payload["sessionRef"]) / "librechat-core.json"
    raw = ack_path.read_text()
    ack = json.loads(raw)
    assert result == {"acknowledged": True, "serviceId": "librechat-core"}
    assert stat.S_IMODE(ack_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(ack_path.parent.stat().st_mode) == 0o700
    assert str(payload["caseToken"]) not in raw
    assert ack["proof"].startswith("hmac-sha256:")
    assert module.acknowledgement_valid(
        ack,
        state_payload=payload,
        process_probe=lambda pid, path: _process(pid, path),
        now=datetime(2026, 8, 25, 0, 0, 3, tzinfo=timezone.utc),
    )


def test_acknowledgement_rejects_a_forged_caller_pid(module, tmp_path):
    with pytest.raises(ValueError):
        module.acknowledge(
            state_payload=_state(),
            ack_root=tmp_path / "acks",
            service_id="librechat-core",
            pid=99999,
            parent_pid=os.getpid(),
            executable_path=Path(sys.executable),
            process_probe=lambda pid, path: _process(pid, path),
        )


def test_process_must_start_after_session_activation(module, tmp_path):
    with pytest.raises(ValueError):
        module.acknowledge(
            state_payload=_state(),
            ack_root=tmp_path / "acks",
            service_id="librechat-core",
            pid=os.getpid(),
            parent_pid=os.getpid(),
            executable_path=Path(sys.executable),
            process_probe=lambda pid, path: {
                **_process(pid, path),
                "startedAt": "2026-08-24T23:59:59.000+00:00",
            },
            now=datetime(2026, 8, 25, 0, 0, 1, tzinfo=timezone.utc),
        )


def test_status_fails_closed_until_every_required_live_service_acknowledges(
    module, tmp_path, service_processes
):
    payload = _state()
    ack_root = tmp_path / "acks"
    probe = lambda pid, path: _process(pid, path)
    now = datetime(2026, 8, 25, 0, 0, 2, tzinfo=timezone.utc)
    core = service_processes["librechat-core"]

    module.acknowledge(
        state_payload=payload,
        ack_root=ack_root,
        service_id="librechat-core",
        pid=core["pid"],
        parent_pid=core["pid"],
        executable_path=core["executable"],
        process_probe=probe,
        now=now,
    )
    partial = module.restart_status(
        payload, ack_root=ack_root, process_probe=probe, now=now
    )
    assert partial["restartState"] == "waiting"
    assert partial["acknowledgedServices"] == ["librechat-core"]
    assert partial["missingServices"] == ["glasshive-runtime", "telegram-bot"]

    for service_id in ("glasshive-runtime", "telegram-bot"):
        process = service_processes[service_id]
        module.acknowledge(
            state_payload=payload,
            ack_root=ack_root,
            service_id=service_id,
            pid=process["pid"],
            parent_pid=process["pid"],
            executable_path=process["executable"],
            process_probe=probe,
            now=now,
        )
    complete = module.restart_status(
        payload, ack_root=ack_root, process_probe=probe, now=now
    )
    assert complete["caseId"] == payload["caseId"]
    assert complete["sessionRef"] == payload["sessionRef"]
    assert complete["restartState"] == "ready"
    assert complete["missingServices"] == []
    assert complete["serviceAckDigest"].startswith("sha256:")


def test_status_rejects_a_signed_acknowledgement_copied_to_another_service_filename(
    module, tmp_path, service_processes
):
    payload = _state("TR-026")
    ack_root = tmp_path / "acks"
    core = service_processes["librechat-core"]
    probe = lambda pid, path: _process(pid, path)
    now = datetime(2026, 8, 25, 0, 0, 2, tzinfo=timezone.utc)
    module.acknowledge(
        state_payload=payload,
        ack_root=ack_root,
        service_id="librechat-core",
        pid=core["pid"],
        parent_pid=core["pid"],
        executable_path=core["executable"],
        process_probe=probe,
        now=now,
    )

    session_root = ack_root / str(payload["sessionRef"])
    copied_acknowledgement = session_root / "telegram-bot.json"
    copied_acknowledgement.write_bytes(
        (session_root / "librechat-core.json").read_bytes()
    )
    copied_acknowledgement.chmod(0o600)

    status = module.restart_status(
        payload, ack_root=ack_root, process_probe=probe, now=now
    )

    assert status["restartState"] == "waiting"
    assert status["acknowledgedServices"] == ["librechat-core"]
    assert status["missingServices"] == ["telegram-bot"]


def test_probe_rejects_an_arbitrary_executable_that_the_live_process_does_not_run(
    module, tmp_path
):
    spoofed_executable = tmp_path / "claimed-service-executable"
    spoofed_executable.write_bytes(b"#!/bin/sh\nexit 0\n")
    spoofed_executable.chmod(0o755)

    with pytest.raises(ValueError, match="process|executable"):
        module.probe_process(os.getpid(), spoofed_executable)


def test_probe_fails_closed_when_kernel_owned_process_identity_is_unavailable(
    module, monkeypatch
):
    unavailable = SimpleNamespace(_live_process_image_and_argv=lambda _pid: None)
    monkeypatch.setattr(
        module.runtime_control, "_release_gate_module", lambda: unavailable
    )

    with pytest.raises(ValueError, match="process"):
        module.probe_process(os.getpid(), Path(sys.executable))


def test_probe_rejects_a_live_process_owned_by_another_user(module, monkeypatch):
    def foreign_owner(argv, **_kwargs):
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=f"{os.geteuid() + 1} Tue Aug 25 00:00:01 2026\n",
            stderr="",
        )

    monkeypatch.setattr(module.subprocess, "run", foreign_owner)

    with pytest.raises(ValueError, match="process identity"):
        module.probe_process(os.getpid(), Path(sys.executable))


def test_process_inspection_never_uses_a_path_supplied_ps(
    module, tmp_path, monkeypatch
):
    forged_ps = tmp_path / "ps"
    forged_ps.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    forged_ps.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setattr(module.os, "access", lambda *_args: False)

    with pytest.raises(ValueError, match="inspection is unavailable"):
        module._ps_path()


def test_probe_preserves_a_genuine_interpreter_executed_service_wrapper(
    module, tmp_path
):
    wrapper = tmp_path / "service-wrapper"
    wrapper.write_text(
        f"#!{sys.executable}\nimport time\ntime.sleep(30)\n",
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    child = subprocess.Popen(
        [str(wrapper)],
        cwd=tmp_path,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        identity = _wait_until_ready(lambda: module.probe_process(child.pid, wrapper))

        assert identity["pid"] == child.pid
        assert identity["executablePath"] == str(wrapper.resolve())
        assert identity["executableSha256"] == module._sha256_file(wrapper)
    finally:
        child.terminate()
        child.wait(timeout=5)


def test_claimed_wrapper_accepts_the_exact_macos_python_framework_image(
    module, tmp_path, monkeypatch
):
    framework_root = tmp_path / "Python.framework" / "Versions" / "3.12"
    interpreter = framework_root / "bin" / "python3.12"
    runtime_image = (
        framework_root
        / "Resources"
        / "Python.app"
        / "Contents"
        / "MacOS"
        / "Python"
    )
    wrapper = tmp_path / "service-wrapper"
    for executable in (interpreter, runtime_image):
        executable.parent.mkdir(parents=True, exist_ok=True)
        executable.write_text("runtime\n", encoding="utf-8")
    wrapper.write_text(f"#!{interpreter}\n", encoding="utf-8")

    inspector = SimpleNamespace(
        _script_interpreter=lambda _path: (interpreter.resolve(), (str(interpreter),))
    )
    monkeypatch.setattr(module.sys, "platform", "darwin")
    monkeypatch.setattr(module, "_process_inspector", lambda: inspector)
    monkeypatch.setattr(module, "_process_cwd", lambda _pid: tmp_path)

    assert module._claimed_executable_is_live(
        wrapper.resolve(),
        pid=os.getpid(),
        live_image=runtime_image.resolve(),
        live_argv=(str(runtime_image), str(wrapper)),
    )


@pytest.mark.parametrize(
    ("claimed_service", "actual_service"),
    (
        ("telegram-bot", "librechat-core"),
        ("glasshive-runtime", "telegram-bot"),
        ("telegram-bot", "glasshive-runtime"),
        ("librechat-core", "glasshive-runtime"),
    ),
)
def test_acknowledgement_rejects_a_genuine_process_from_another_service(
    module, tmp_path, service_processes, claimed_service, actual_service
):
    process = service_processes[actual_service]

    with pytest.raises(ValueError, match="process"):
        module.acknowledge(
            state_payload=_state(),
            ack_root=tmp_path / "acks",
            service_id=claimed_service,
            pid=process["pid"],
            parent_pid=process["pid"],
            executable_path=process["executable"],
            now=datetime(2026, 8, 25, 0, 0, 2, tzinfo=timezone.utc),
        )


def test_acknowledgement_rejects_a_canonical_entrypoint_supplied_only_as_process_data(
    module, tmp_path, service_processes
):
    telegram = service_processes["telegram-bot"]
    telegram_entrypoint = (
        telegram["installed"]
        / "viventium_v0_4"
        / "telegram-viventium"
        / "TelegramVivBot"
        / "bot.py"
    )
    unrelated = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)", str(telegram_entrypoint)],
        cwd=telegram_entrypoint.parent,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_until_ready(
            lambda: _process_argv_contains(
                module, unrelated.pid, "-c", str(telegram_entrypoint)
            )
        )
        with pytest.raises(ValueError, match="process"):
            module.acknowledge(
                state_payload=_state("TR-026"),
                ack_root=tmp_path / "acks",
                service_id="telegram-bot",
                pid=unrelated.pid,
                parent_pid=unrelated.pid,
                executable_path=Path(sys.executable),
                now=datetime(2026, 8, 25, 0, 0, 2, tzinfo=timezone.utc),
            )
    finally:
        unrelated.terminate()
        unrelated.wait(timeout=5)


@pytest.mark.parametrize(
    ("service_id", "stdin_program"),
    (
        ("telegram-bot", "import time\ntime.sleep(30)\n"),
        ("librechat-core", "setInterval(() => {}, 1000);\n"),
    ),
)
def test_acknowledgement_rejects_stdin_execution_with_a_real_entrypoint_argument(
    module, tmp_path, service_processes, service_id, stdin_program
):
    service = service_processes[service_id]
    installed = service["installed"]
    entrypoint = (
        installed / "viventium_v0_4" / "LibreChat" / "api" / "server" / "index.js"
        if service_id == "librechat-core"
        else installed
        / "viventium_v0_4"
        / "telegram-viventium"
        / "TelegramVivBot"
        / "bot.py"
    )
    unrelated = subprocess.Popen(
        [str(service["executable"]), "-", str(entrypoint)],
        cwd=entrypoint.parent,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    assert unrelated.stdin is not None
    unrelated.stdin.write(stdin_program)
    unrelated.stdin.close()
    try:
        _wait_until_ready(
            lambda: _process_argv_contains(
                module, unrelated.pid, "-", str(entrypoint)
            )
        )
        with pytest.raises(ValueError, match="process"):
            module.acknowledge(
                state_payload=_state("TR-026"),
                ack_root=tmp_path / "acks",
                service_id=service_id,
                pid=unrelated.pid,
                parent_pid=unrelated.pid,
                executable_path=service["executable"],
                now=datetime(2026, 8, 25, 0, 0, 2, tzinfo=timezone.utc),
            )
    finally:
        unrelated.terminate()
        unrelated.wait(timeout=5)


def test_acknowledgement_fails_closed_when_verified_process_cwd_is_unavailable(
    module, tmp_path, service_processes, monkeypatch
):
    core = service_processes["librechat-core"]

    def unavailable(_pid):
        raise ValueError("process working directory is unavailable")

    monkeypatch.setattr(module, "_process_cwd", unavailable)

    with pytest.raises(ValueError, match="service process"):
        module.acknowledge(
            state_payload=_state("TR-026"),
            ack_root=tmp_path / "acks",
            service_id="librechat-core",
            pid=core["pid"],
            parent_pid=core["pid"],
            executable_path=core["executable"],
            process_probe=lambda pid, path: _process(pid, path),
            now=datetime(2026, 8, 25, 0, 0, 2, tzinfo=timezone.utc),
        )


def test_status_rejects_distinct_signed_service_acknowledgements_for_the_same_pid(
    module, tmp_path, service_processes, monkeypatch
):
    payload = _state("TR-026")
    ack_root = tmp_path / "acks"
    core = service_processes["librechat-core"]
    probe = lambda pid, path: _process(pid, path)
    now = datetime(2026, 8, 25, 0, 0, 2, tzinfo=timezone.utc)
    module.acknowledge(
        state_payload=payload,
        ack_root=ack_root,
        service_id="librechat-core",
        pid=core["pid"],
        parent_pid=core["pid"],
        executable_path=core["executable"],
        process_probe=probe,
        now=now,
    )
    session_root = ack_root / str(payload["sessionRef"])
    genuine = json.loads((session_root / "librechat-core.json").read_text())
    unsigned = {
        **{key: value for key, value in genuine.items() if key != "proof"},
        "serviceId": "telegram-bot",
    }
    replayed = {**unsigned, "proof": module._proof(unsigned, payload["caseToken"])}
    module.runtime_control._write_private_json(
        session_root / "telegram-bot.json", replayed
    )
    monkeypatch.setattr(module, "_service_process_identity_valid", lambda *_args: True)

    status = module.restart_status(
        payload, ack_root=ack_root, process_probe=probe, now=now
    )

    assert status["restartState"] == "waiting"
    assert status["acknowledgedServices"] == ["librechat-core"]
    assert status["missingServices"] == ["telegram-bot"]


def test_status_rejects_distinct_pids_with_the_same_live_process_start_identity(
    module, tmp_path, service_processes
):
    payload = _state("TR-026")
    ack_root = tmp_path / "acks"
    duplicate_marker = "sha256:" + "f" * 64
    probe = lambda pid, path: _process(pid, path, marker=duplicate_marker)
    now = datetime(2026, 8, 25, 0, 0, 2, tzinfo=timezone.utc)
    for service_id in ("librechat-core", "telegram-bot"):
        process = service_processes[service_id]
        module.acknowledge(
            state_payload=payload,
            ack_root=ack_root,
            service_id=service_id,
            pid=process["pid"],
            parent_pid=process["pid"],
            executable_path=process["executable"],
            process_probe=probe,
            now=now,
        )

    status = module.restart_status(
        payload, ack_root=ack_root, process_probe=probe, now=now
    )

    assert status["restartState"] == "waiting"
    assert status["acknowledgedServices"] == ["librechat-core"]
    assert status["missingServices"] == ["telegram-bot"]


def test_status_rejects_duplicate_required_service_identifiers(
    module, tmp_path, service_processes, monkeypatch
):
    payload = _state("REL-UC-004")
    ack_root = tmp_path / "acks"
    core = service_processes["librechat-core"]
    probe = lambda pid, path: _process(pid, path)
    now = datetime(2026, 8, 25, 0, 0, 2, tzinfo=timezone.utc)
    module.acknowledge(
        state_payload=payload,
        ack_root=ack_root,
        service_id="librechat-core",
        pid=core["pid"],
        parent_pid=core["pid"],
        executable_path=core["executable"],
        process_probe=probe,
        now=now,
    )
    monkeypatch.setitem(
        module.REQUIRED_SERVICES,
        "REL-UC-004",
        ("librechat-core", "librechat-core"),
    )

    with pytest.raises(ValueError, match="service"):
        module.restart_status(payload, ack_root=ack_root, process_probe=probe, now=now)


def test_distinct_real_user_owned_service_processes_produce_one_verified_ready_digest(
    module, tmp_path, service_processes
):
    now = datetime.now(timezone.utc)
    payload = _state()
    payload["startedAt"] = (now - timedelta(seconds=10)).isoformat(
        timespec="milliseconds"
    )
    payload["expiresAt"] = (now + timedelta(minutes=10)).isoformat(
        timespec="milliseconds"
    )
    ack_root = tmp_path / "acks"

    for service_id, process in service_processes.items():
        assert module.acknowledge(
            state_payload=payload,
            ack_root=ack_root,
            service_id=service_id,
            pid=process["pid"],
            parent_pid=process["pid"],
            executable_path=process["executable"],
            now=now,
        ) == {"acknowledged": True, "serviceId": service_id}

    status = module.restart_status(payload, ack_root=ack_root, now=now)

    assert set(status) == {
        "acknowledgedServices",
        "caseId",
        "missingServices",
        "requiredServices",
        "restartState",
        "serviceAckDigest",
        "sessionRef",
    }
    assert status["caseId"] == payload["caseId"]
    assert status["sessionRef"] == payload["sessionRef"]
    assert status["restartState"] == "ready"
    assert status["acknowledgedServices"] == list(
        module.REQUIRED_SERVICES[payload["caseId"]]
    )
    assert status["missingServices"] == []
    assert status["serviceAckDigest"].startswith("sha256:")
    assert str(payload["caseToken"]) not in json.dumps(status)


@pytest.mark.parametrize("mutation", ["proof", "sessionRef", "artifactIdentityDigest"])
def test_status_rejects_tampered_or_replayed_acknowledgements(
    module, tmp_path, mutation, service_processes
):
    payload = _state("REL-UC-004")
    ack_root = tmp_path / "acks"
    core = service_processes["librechat-core"]
    probe = lambda pid, path: _process(pid, path)
    now = datetime(2026, 8, 25, 0, 0, 2, tzinfo=timezone.utc)
    module.acknowledge(
        state_payload=payload,
        ack_root=ack_root,
        service_id="librechat-core",
        pid=core["pid"],
        parent_pid=core["pid"],
        executable_path=core["executable"],
        process_probe=probe,
        now=now,
    )
    ack_path = ack_root / str(payload["sessionRef"]) / "librechat-core.json"
    ack = json.loads(ack_path.read_text())
    ack[mutation] = "hmac-sha256:" + "0" * 64 if mutation == "proof" else "wrong"
    ack_path.write_text(json.dumps(ack))
    ack_path.chmod(0o600)

    status = module.restart_status(
        payload, ack_root=ack_root, process_probe=probe, now=now
    )
    assert status["restartState"] == "waiting"
    assert status["acknowledgedServices"] == []
    assert status["missingServices"] == ["librechat-core"]


def test_status_detects_pid_reuse_or_process_replacement(
    module, tmp_path, service_processes
):
    payload = _state("REL-UC-004")
    ack_root = tmp_path / "acks"
    core = service_processes["librechat-core"]
    module.acknowledge(
        state_payload=payload,
        ack_root=ack_root,
        service_id="librechat-core",
        pid=core["pid"],
        parent_pid=core["pid"],
        executable_path=core["executable"],
        process_probe=lambda pid, path: _process(pid, path),
        now=datetime(2026, 8, 25, 0, 0, 2, tzinfo=timezone.utc),
    )

    status = module.restart_status(
        payload,
        ack_root=ack_root,
        process_probe=lambda pid, path: _process(
            pid, path, marker="sha256:" + "f" * 64
        ),
        now=datetime(2026, 8, 25, 0, 0, 3, tzinfo=timezone.utc),
    )
    assert status["restartState"] == "waiting"
    assert status["missingServices"] == ["librechat-core"]


def test_clear_removes_only_the_exact_session_directory(module, tmp_path):
    ack_root = tmp_path / "acks"
    target = ack_root / "qa_target_123456789012"
    other = ack_root / "qa_other_123456789012"
    target.mkdir(parents=True)
    other.mkdir()
    (target / "librechat-core.json").write_text("{}")
    module.clear_acknowledgements(ack_root, "qa_target_123456789012")
    assert not target.exists()
    assert other.exists()


def test_cli_failure_is_redacted_and_never_echoes_private_values(tmp_path):
    secret = "never-print-this-token"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "acknowledge",
            "--service-id",
            "librechat-core",
            "--pid",
            "1",
            "--executable",
            str(Path(sys.executable)),
        ],
        env={**os.environ, "VIVENTIUM_LOCAL_QA_CASE_TOKEN": secret},
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 2
    assert json.loads(result.stderr) == {"error": "operation_failed"}
    assert secret not in result.stdout + result.stderr

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import textwrap
import time

import pytest


ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "scripts" / "viventium" / "qa_storage_guard.py"
POLICY = ROOT / "qa" / "installer-resilience" / "storage-policy.json"


def _write_executable(path: Path, source: str) -> None:
    path.write_text(textwrap.dedent(source).lstrip(), encoding="utf-8")
    path.chmod(0o755)


def _fake_tools(tmp_path: Path) -> tuple[Path, Path, Path]:
    tool_state = tmp_path / "tool-state"
    tool_state.mkdir()
    tart = tmp_path / "fake-tart"
    docker = tmp_path / "fake-docker"

    _write_executable(
        tart,
        """
        #!/usr/bin/env python3
        import json
        import os
        from pathlib import Path
        import sys

        state = Path(os.environ["FAKE_TOOL_STATE"])
        vms = state / "vms.json"
        events = state / "tart-events.jsonl"
        names = json.loads(vms.read_text()) if vms.exists() else []
        with events.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "argv": sys.argv[1:],
                "no_auto_prune": os.environ.get("TART_NO_AUTO_PRUNE"),
            }) + "\\n")
        if sys.argv[1:] == ["list", "--format", "json"]:
            print(json.dumps([{"Name": name} for name in names]))
        elif len(sys.argv) == 4 and sys.argv[1] == "clone":
            names.append(sys.argv[3])
            vms.write_text(json.dumps(names))
            if os.environ.get("FAKE_TART_CLONE_FAIL_AFTER_CREATE") == "1":
                raise SystemExit(2)
        elif len(sys.argv) == 3 and sys.argv[1] == "delete":
            if sys.argv[2] not in names:
                raise SystemExit(2)
            names.remove(sys.argv[2])
            vms.write_text(json.dumps(names))
        else:
            raise SystemExit(64)
        """,
    )
    _write_executable(
        docker,
        """
        #!/usr/bin/env python3
        import json
        import os
        from pathlib import Path
        import sys

        state = Path(os.environ["FAKE_TOOL_STATE"])
        payload = json.loads((state / "docker.json").read_text())
        argv = sys.argv[1:]
        if argv == ["context", "show"]:
            print(payload["context"])
        elif argv == ["ps", "-aq", "--no-trunc"]:
            print("\\n".join(payload["containers"]))
        elif argv == ["volume", "ls", "--quiet"]:
            print("\\n".join(payload["volumes"]))
        elif argv == ["image", "ls", "--no-trunc", "--quiet"]:
            print("\\n".join(payload["images"]))
        else:
            raise SystemExit(64)
        """,
    )
    (tool_state / "docker.json").write_text(
        json.dumps(
            {
                "context": "desktop-linux",
                "containers": ["container-before"],
                "volumes": ["volume-before"],
                "images": ["sha256:image-before"],
            }
        ),
        encoding="utf-8",
    )
    return tart, docker, tool_state


def _policy(tmp_path: Path, **overrides: int | str) -> Path:
    payload = json.loads(POLICY.read_text(encoding="utf-8"))
    payload.update(overrides)
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _guard(
    tmp_path: Path,
    *args: str,
    env_updates: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(env_updates or {})
    return subprocess.run(
        [sys.executable, str(GUARD), *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _load_guard_module() -> object:
    spec = importlib.util.spec_from_file_location("qa_storage_guard_under_test", GUARD)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _prepare(
    tmp_path: Path,
    tart: Path,
    docker: Path,
    tool_state: Path,
    *,
    run_id: str = "storage-case",
    policy: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    candidate = tmp_path / "candidate"
    candidate.mkdir(exist_ok=True)
    docker_disk = tmp_path / "Docker.raw"
    docker_disk.touch(exist_ok=True)
    return _guard(
        tmp_path,
        "prepare",
        "--run-id",
        run_id,
        "--vm-name",
        f"viventium-qa-{run_id}",
        "--candidate",
        str(candidate),
        "--state-root",
        str(tmp_path / "guard-state"),
        "--policy",
        str(
            policy
            or _policy(
                tmp_path,
                minimum_free_bytes_before_run=1,
                abort_below_free_bytes=1,
            )
        ),
        "--tart",
        str(tart),
        "--docker",
        str(docker),
        "--docker-disk",
        str(docker_disk),
        env_updates={"FAKE_TOOL_STATE": str(tool_state)},
    )


def test_prepare_creates_exclusive_persistent_receipt_and_refuses_a_second_run(
    tmp_path: Path,
) -> None:
    tart, docker, tool_state = _fake_tools(tmp_path)

    first = _prepare(tmp_path, tart, docker, tool_state)
    second = _prepare(tmp_path, tart, docker, tool_state, run_id="another-case")

    assert first.returncode == 0, first.stderr
    assert second.returncode != 0
    assert "CLEANUP_REQUIRED" in second.stderr
    receipt = json.loads(
        (tmp_path / "guard-state" / "runs" / "storage-case.json").read_text(encoding="utf-8")
    )
    assert receipt["phase"] == "PREPARED"
    assert receipt["vm_name"] == "viventium-qa-storage-case"
    assert receipt["docker_baseline"]["volumes"] == ["volume-before"]


def test_prepare_fails_closed_when_any_qa_vm_already_exists(tmp_path: Path) -> None:
    tart, docker, tool_state = _fake_tools(tmp_path)
    (tool_state / "vms.json").write_text(json.dumps(["viventium-qa-leftover"]), encoding="utf-8")

    result = _prepare(tmp_path, tart, docker, tool_state)

    assert result.returncode != 0
    assert "viventium-qa-leftover" in result.stderr
    assert not (tmp_path / "guard-state" / "active-lease.json").exists()


def test_prepare_refuses_a_broad_existing_state_directory_without_chmodding_it(
    tmp_path: Path,
) -> None:
    tart, docker, tool_state = _fake_tools(tmp_path)
    state_root = tmp_path / "guard-state"
    state_root.mkdir(mode=0o755)

    result = _prepare(tmp_path, tart, docker, tool_state)

    assert result.returncode != 0
    assert "owner-only" in result.stderr
    assert state_root.stat().st_mode & 0o777 == 0o755


def test_clone_sets_no_auto_prune_and_records_only_the_exact_owned_vm(tmp_path: Path) -> None:
    tart, docker, tool_state = _fake_tools(tmp_path)
    prepared = _prepare(tmp_path, tart, docker, tool_state)
    assert prepared.returncode == 0, prepared.stderr

    result = _guard(
        tmp_path,
        "clone",
        "--run-id",
        "storage-case",
        "--state-root",
        str(tmp_path / "guard-state"),
        "--source-vm",
        "macos-base",
        env_updates={"FAKE_TOOL_STATE": str(tool_state)},
    )

    assert result.returncode == 0, result.stderr
    events = [
        json.loads(line)
        for line in (tool_state / "tart-events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    clone_event = next(event for event in events if event["argv"][0] == "clone")
    assert clone_event == {
        "argv": ["clone", "macos-base", "viventium-qa-storage-case"],
        "no_auto_prune": "1",
    }
    receipt = json.loads(
        (tmp_path / "guard-state" / "runs" / "storage-case.json").read_text(encoding="utf-8")
    )
    assert receipt["phase"] == "VM_READY"
    assert receipt["owned_vm_created"] is True


def test_clone_refuses_when_a_new_unowned_qa_vm_appears_after_prepare(tmp_path: Path) -> None:
    tart, docker, tool_state = _fake_tools(tmp_path)
    prepared = _prepare(tmp_path, tart, docker, tool_state)
    assert prepared.returncode == 0, prepared.stderr
    (tool_state / "vms.json").write_text(json.dumps(["viventium-qa-race"]), encoding="utf-8")

    result = _guard(
        tmp_path,
        "clone",
        "--run-id",
        "storage-case",
        "--state-root",
        str(tmp_path / "guard-state"),
        "--source-vm",
        "macos-base",
        env_updates={"FAKE_TOOL_STATE": str(tool_state)},
    )

    assert result.returncode != 0
    assert "viventium-qa-race" in result.stderr
    assert json.loads((tool_state / "vms.json").read_text()) == ["viventium-qa-race"]


def test_run_rejects_shells_prune_globs_and_string_commands(tmp_path: Path) -> None:
    tart, docker, tool_state = _fake_tools(tmp_path)
    prepared = _prepare(tmp_path, tart, docker, tool_state)
    assert prepared.returncode == 0, prepared.stderr

    for argv in (
        ["bash", "-c", "true"],
        ["/usr/bin/env", "bash", "-c", "true"],
        [str(docker), "system", "prune"],
        [str(docker), "rm", "unowned-container"],
        [str(docker), "--context", "other", "rm", "unowned-container"],
        ["printf", "*.raw"],
        ["rm", "target"],
    ):
        result = _guard(
            tmp_path,
            "run",
            "--run-id",
            "storage-case",
            "--state-root",
            str(tmp_path / "guard-state"),
            "--",
            *argv,
            env_updates={"FAKE_TOOL_STATE": str(tool_state)},
        )
        assert result.returncode != 0, argv
        assert "unsafe argv" in result.stderr


def test_run_uses_argv_without_shell_and_completes_a_safe_child(tmp_path: Path) -> None:
    tart, docker, tool_state = _fake_tools(tmp_path)
    prepared = _prepare(tmp_path, tart, docker, tool_state)
    assert prepared.returncode == 0, prepared.stderr
    marker = tmp_path / "marker"
    child = tmp_path / "safe-child"
    _write_executable(
        child,
        """
        #!/usr/bin/env python3
        from pathlib import Path
        import sys
        Path(sys.argv[1]).write_text(sys.argv[2], encoding="utf-8")
        """,
    )

    result = _guard(
        tmp_path,
        "run",
        "--run-id",
        "storage-case",
        "--state-root",
        str(tmp_path / "guard-state"),
        "--",
        str(child),
        str(marker),
        "literal;not-a-shell-command",
        env_updates={"FAKE_TOOL_STATE": str(tool_state)},
    )

    assert result.returncode == 0, result.stderr
    assert marker.read_text(encoding="utf-8") == "literal;not-a-shell-command"


def test_run_aborts_on_free_space_floor_and_leaves_cleanup_required_receipt(tmp_path: Path) -> None:
    tart, docker, tool_state = _fake_tools(tmp_path)
    policy = _policy(
        tmp_path,
        minimum_free_bytes_before_run=1,
        abort_below_free_bytes=10**18,
        sample_interval_seconds=0.01,
    )
    prepared = _prepare(tmp_path, tart, docker, tool_state, policy=policy)
    assert prepared.returncode == 0, prepared.stderr
    child = tmp_path / "long-child"
    _write_executable(
        child,
        """
        #!/usr/bin/env python3
        import time
        time.sleep(10)
        """,
    )

    result = _guard(
        tmp_path,
        "run",
        "--run-id",
        "storage-case",
        "--state-root",
        str(tmp_path / "guard-state"),
        "--",
        str(child),
        env_updates={"FAKE_TOOL_STATE": str(tool_state)},
    )

    assert result.returncode != 0
    assert "free-space floor" in result.stderr
    receipt = json.loads(
        (tmp_path / "guard-state" / "runs" / "storage-case.json").read_text(encoding="utf-8")
    )
    assert receipt["phase"] == "CLEANUP_REQUIRED"
    assert (tmp_path / "guard-state" / "active-lease.json").exists()


def test_interrupt_stops_the_guarded_process_group_and_keeps_cleanup_required(
    tmp_path: Path,
) -> None:
    tart, docker, tool_state = _fake_tools(tmp_path)
    prepared = _prepare(tmp_path, tart, docker, tool_state)
    assert prepared.returncode == 0, prepared.stderr
    child_pid_path = tmp_path / "child.pid"
    child = tmp_path / "interruptible-child"
    _write_executable(
        child,
        """
        #!/usr/bin/env python3
        from pathlib import Path
        import os
        import signal
        import sys
        import time
        Path(sys.argv[1]).write_text(str(os.getpid()), encoding="utf-8")
        signal.signal(signal.SIGTERM, lambda _signum, _frame: raise_system_exit())
        def raise_system_exit():
            raise SystemExit(0)
        time.sleep(20)
        """,
    )
    env = os.environ.copy()
    env["FAKE_TOOL_STATE"] = str(tool_state)
    guard = subprocess.Popen(
        [
            sys.executable,
            str(GUARD),
            "run",
            "--run-id",
            "storage-case",
            "--state-root",
            str(tmp_path / "guard-state"),
            "--",
            str(child),
            str(child_pid_path),
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    child_pid: int | None = None
    try:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not child_pid_path.exists():
            time.sleep(0.02)
        assert child_pid_path.exists()
        child_pid = int(child_pid_path.read_text(encoding="utf-8"))
        guard.send_signal(signal.SIGTERM)
        _, stderr = guard.communicate(timeout=7)

        assert guard.returncode != 0
        assert "interrupted" in stderr
        with pytest.raises(ProcessLookupError):
            os.kill(child_pid, 0)
        receipt = json.loads(
            (tmp_path / "guard-state" / "runs" / "storage-case.json").read_text(encoding="utf-8")
        )
        assert receipt["phase"] == "CLEANUP_REQUIRED"
    finally:
        if guard.poll() is None:
            guard.kill()
            guard.wait(timeout=5)
        if child_pid is not None:
            try:
                os.killpg(child_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def test_normal_leader_exit_kills_background_grandchild_and_fails_closed(
    tmp_path: Path,
) -> None:
    tart, docker, tool_state = _fake_tools(tmp_path)
    prepared = _prepare(tmp_path, tart, docker, tool_state)
    assert prepared.returncode == 0, prepared.stderr
    grandchild_state_path = tmp_path / "grandchild.json"
    child = tmp_path / "background-grandchild"
    _write_executable(
        child,
        """
        #!/usr/bin/env python3
        from pathlib import Path
        import json
        import os
        import signal
        import sys
        import time
        grandchild = os.fork()
        if grandchild == 0:
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            Path(sys.argv[1]).write_text(
                json.dumps({"pid": os.getpid(), "pgid": os.getpgrp()}),
                encoding="utf-8",
            )
            time.sleep(30)
            raise SystemExit(0)
        raise SystemExit(0)
        """,
    )
    env = os.environ.copy()
    env["FAKE_TOOL_STATE"] = str(tool_state)
    guard = subprocess.Popen(
        [
            sys.executable,
            str(GUARD),
            "run",
            "--run-id",
            "storage-case",
            "--state-root",
            str(tmp_path / "guard-state"),
            "--",
            str(child),
            str(grandchild_state_path),
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    grandchild_state: dict[str, int] | None = None
    try:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not grandchild_state_path.exists():
            time.sleep(0.02)
        assert grandchild_state_path.exists()
        grandchild_state = json.loads(grandchild_state_path.read_text(encoding="utf-8"))
        _, stderr = guard.communicate(timeout=8)

        assert guard.returncode != 0
        assert "descendant" in stderr
        with pytest.raises(ProcessLookupError):
            os.kill(grandchild_state["pid"], 0)
        receipt = json.loads(
            (tmp_path / "guard-state" / "runs" / "storage-case.json").read_text(encoding="utf-8")
        )
        assert receipt["phase"] == "CLEANUP_REQUIRED"
    finally:
        if guard.poll() is None:
            guard.kill()
            guard.wait(timeout=5)
        if grandchild_state is not None:
            try:
                os.killpg(grandchild_state["pgid"], signal.SIGKILL)
            except ProcessLookupError:
                pass


def test_leader_exit_on_term_cannot_suppress_kill_of_owned_descendant(
    tmp_path: Path,
) -> None:
    tart, docker, tool_state = _fake_tools(tmp_path)
    prepared = _prepare(tmp_path, tart, docker, tool_state)
    assert prepared.returncode == 0, prepared.stderr
    process_ids_path = tmp_path / "process-ids.json"
    child = tmp_path / "term-leader-with-grandchild"
    _write_executable(
        child,
        """
        #!/usr/bin/env python3
        from pathlib import Path
        import json
        import os
        import signal
        import sys
        import time
        grandchild = os.fork()
        if grandchild == 0:
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            time.sleep(30)
            raise SystemExit(0)
        signal.signal(signal.SIGTERM, lambda _signum, _frame: os._exit(0))
        Path(sys.argv[1]).write_text(
            json.dumps({"leader": os.getpid(), "grandchild": grandchild}),
            encoding="utf-8",
        )
        time.sleep(30)
        """,
    )
    env = os.environ.copy()
    env["FAKE_TOOL_STATE"] = str(tool_state)
    guard = subprocess.Popen(
        [
            sys.executable,
            str(GUARD),
            "run",
            "--run-id",
            "storage-case",
            "--state-root",
            str(tmp_path / "guard-state"),
            "--",
            str(child),
            str(process_ids_path),
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    process_ids: dict[str, int] | None = None
    try:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not process_ids_path.exists():
            time.sleep(0.02)
        assert process_ids_path.exists()
        process_ids = json.loads(process_ids_path.read_text(encoding="utf-8"))
        guard.send_signal(signal.SIGTERM)
        _, stderr = guard.communicate(timeout=8)

        assert guard.returncode != 0
        assert "interrupted" in stderr
        for process_id in process_ids.values():
            with pytest.raises(ProcessLookupError):
                os.kill(process_id, 0)
        receipt = json.loads(
            (tmp_path / "guard-state" / "runs" / "storage-case.json").read_text(encoding="utf-8")
        )
        assert receipt["phase"] == "CLEANUP_REQUIRED"
    finally:
        if guard.poll() is None:
            guard.kill()
            guard.wait(timeout=5)
        if process_ids is not None:
            try:
                os.killpg(process_ids["leader"], signal.SIGKILL)
            except ProcessLookupError:
                pass


def test_process_group_uncertainty_persists_cleanup_required(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tart, docker, tool_state = _fake_tools(tmp_path)
    prepared = _prepare(tmp_path, tart, docker, tool_state)
    assert prepared.returncode == 0, prepared.stderr
    module = _load_guard_module()
    uncertainty = "owned process group could not be proven empty"
    monkeypatch.setattr(module, "_run_monitored", lambda _receipt, _argv: (0, uncertainty))

    with pytest.raises(module.GuardError, match=uncertainty):
        module.command_run(
            argparse.Namespace(
                run_id="storage-case",
                state_root=str(tmp_path / "guard-state"),
                argv=["--", "/usr/bin/true"],
            )
        )

    receipt = json.loads(
        (tmp_path / "guard-state" / "runs" / "storage-case.json").read_text(encoding="utf-8")
    )
    assert receipt["phase"] == "CLEANUP_REQUIRED"
    assert receipt["detail"] == uncertainty


def test_run_fails_if_a_preexisting_docker_resource_disappears(tmp_path: Path) -> None:
    tart, docker, tool_state = _fake_tools(tmp_path)
    prepared = _prepare(tmp_path, tart, docker, tool_state)
    assert prepared.returncode == 0, prepared.stderr
    mutator = tmp_path / "docker-mutator"
    _write_executable(
        mutator,
        """
        #!/usr/bin/env python3
        import json
        from pathlib import Path
        import sys
        path = Path(sys.argv[1])
        payload = json.loads(path.read_text())
        payload["volumes"] = []
        path.write_text(json.dumps(payload))
        """,
    )

    result = _guard(
        tmp_path,
        "run",
        "--run-id",
        "storage-case",
        "--state-root",
        str(tmp_path / "guard-state"),
        "--",
        str(mutator),
        str(tool_state / "docker.json"),
        env_updates={"FAKE_TOOL_STATE": str(tool_state)},
    )

    assert result.returncode != 0
    assert "pre-existing Docker volume disappeared" in result.stderr
    receipt = json.loads(
        (tmp_path / "guard-state" / "runs" / "storage-case.json").read_text(encoding="utf-8")
    )
    assert receipt["phase"] == "CLEANUP_REQUIRED"


def test_cleanup_deletes_only_receipt_owned_vm_and_releases_lease(tmp_path: Path) -> None:
    tart, docker, tool_state = _fake_tools(tmp_path)
    prepared = _prepare(tmp_path, tart, docker, tool_state)
    assert prepared.returncode == 0, prepared.stderr
    cloned = _guard(
        tmp_path,
        "clone",
        "--run-id",
        "storage-case",
        "--state-root",
        str(tmp_path / "guard-state"),
        "--source-vm",
        "macos-base",
        env_updates={"FAKE_TOOL_STATE": str(tool_state)},
    )
    assert cloned.returncode == 0, cloned.stderr

    result = _guard(
        tmp_path,
        "cleanup",
        "--run-id",
        "storage-case",
        "--confirm-run-id",
        "storage-case",
        "--state-root",
        str(tmp_path / "guard-state"),
        env_updates={"FAKE_TOOL_STATE": str(tool_state)},
    )

    assert result.returncode == 0, result.stderr
    assert json.loads((tool_state / "vms.json").read_text()) == []
    assert not (tmp_path / "guard-state" / "active-lease.json").exists()
    receipt = json.loads(
        (tmp_path / "guard-state" / "runs" / "storage-case.json").read_text(encoding="utf-8")
    )
    assert receipt["phase"] == "COMPLETE"
    events = [
        json.loads(line)
        for line in (tool_state / "tart-events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert ["delete", "viventium-qa-storage-case"] in [event["argv"] for event in events]


def test_cleanup_refuses_name_mismatch_or_unowned_vm_without_deleting_anything(tmp_path: Path) -> None:
    tart, docker, tool_state = _fake_tools(tmp_path)
    prepared = _prepare(tmp_path, tart, docker, tool_state)
    assert prepared.returncode == 0, prepared.stderr
    (tool_state / "vms.json").write_text(json.dumps(["viventium-qa-other"]), encoding="utf-8")

    wrong_confirmation = _guard(
        tmp_path,
        "cleanup",
        "--run-id",
        "storage-case",
        "--confirm-run-id",
        "wrong-case",
        "--state-root",
        str(tmp_path / "guard-state"),
        env_updates={"FAKE_TOOL_STATE": str(tool_state)},
    )
    unowned = _guard(
        tmp_path,
        "cleanup",
        "--run-id",
        "storage-case",
        "--confirm-run-id",
        "storage-case",
        "--state-root",
        str(tmp_path / "guard-state"),
        env_updates={"FAKE_TOOL_STATE": str(tool_state)},
    )

    assert wrong_confirmation.returncode != 0
    assert unowned.returncode != 0
    assert "unowned QA VM" in unowned.stderr
    assert json.loads((tool_state / "vms.json").read_text()) == ["viventium-qa-other"]


def test_cleanup_never_deletes_a_partial_clone_without_created_ownership_proof(
    tmp_path: Path,
) -> None:
    tart, docker, tool_state = _fake_tools(tmp_path)
    prepared = _prepare(tmp_path, tart, docker, tool_state)
    assert prepared.returncode == 0, prepared.stderr
    clone = _guard(
        tmp_path,
        "clone",
        "--run-id",
        "storage-case",
        "--state-root",
        str(tmp_path / "guard-state"),
        "--source-vm",
        "macos-base",
        env_updates={
            "FAKE_TOOL_STATE": str(tool_state),
            "FAKE_TART_CLONE_FAIL_AFTER_CREATE": "1",
        },
    )
    assert clone.returncode != 0

    cleanup = _guard(
        tmp_path,
        "cleanup",
        "--run-id",
        "storage-case",
        "--confirm-run-id",
        "storage-case",
        "--state-root",
        str(tmp_path / "guard-state"),
        env_updates={"FAKE_TOOL_STATE": str(tool_state)},
    )

    assert cleanup.returncode != 0
    assert "not owned" in cleanup.stderr
    assert json.loads((tool_state / "vms.json").read_text()) == ["viventium-qa-storage-case"]
    events = [
        json.loads(line)
        for line in (tool_state / "tart-events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert ["delete", "viventium-qa-storage-case"] not in [event["argv"] for event in events]


def test_cleanup_records_cleanup_required_if_docker_baseline_cannot_be_proven(
    tmp_path: Path,
) -> None:
    tart, docker, tool_state = _fake_tools(tmp_path)
    prepared = _prepare(tmp_path, tart, docker, tool_state)
    assert prepared.returncode == 0, prepared.stderr
    payload = json.loads((tool_state / "docker.json").read_text(encoding="utf-8"))
    payload["volumes"] = []
    (tool_state / "docker.json").write_text(json.dumps(payload), encoding="utf-8")

    result = _guard(
        tmp_path,
        "cleanup",
        "--run-id",
        "storage-case",
        "--confirm-run-id",
        "storage-case",
        "--state-root",
        str(tmp_path / "guard-state"),
        env_updates={"FAKE_TOOL_STATE": str(tool_state)},
    )

    assert result.returncode != 0
    receipt = json.loads(
        (tmp_path / "guard-state" / "runs" / "storage-case.json").read_text(encoding="utf-8")
    )
    assert receipt["phase"] == "CLEANUP_REQUIRED"
    assert (tmp_path / "guard-state" / "active-lease.json").exists()


@pytest.mark.parametrize(
    ("resource_key", "synthetic_id", "expected_message"),
    [
        ("containers", "qa-container-after", "post-baseline Docker container remains"),
        ("volumes", "qa-volume-after", "post-baseline Docker volume remains"),
        ("images", "sha256:qa-image-after", "post-baseline Docker image remains"),
    ],
)
def test_cleanup_fails_closed_when_a_post_baseline_docker_resource_remains(
    tmp_path: Path,
    resource_key: str,
    synthetic_id: str,
    expected_message: str,
) -> None:
    tart, docker, tool_state = _fake_tools(tmp_path)
    prepared = _prepare(tmp_path, tart, docker, tool_state)
    assert prepared.returncode == 0, prepared.stderr
    payload = json.loads((tool_state / "docker.json").read_text(encoding="utf-8"))
    payload[resource_key].append(synthetic_id)
    (tool_state / "docker.json").write_text(json.dumps(payload), encoding="utf-8")

    result = _guard(
        tmp_path,
        "cleanup",
        "--run-id",
        "storage-case",
        "--confirm-run-id",
        "storage-case",
        "--state-root",
        str(tmp_path / "guard-state"),
        env_updates={"FAKE_TOOL_STATE": str(tool_state)},
    )

    assert result.returncode != 0
    assert expected_message in result.stderr
    assert synthetic_id in json.loads(
        (tool_state / "docker.json").read_text(encoding="utf-8")
    )[resource_key]
    receipt = json.loads(
        (tmp_path / "guard-state" / "runs" / "storage-case.json").read_text(encoding="utf-8")
    )
    assert receipt["phase"] == "CLEANUP_REQUIRED"


def test_completed_run_id_cannot_be_reused_and_does_not_strand_a_new_lease(
    tmp_path: Path,
) -> None:
    tart, docker, tool_state = _fake_tools(tmp_path)
    prepared = _prepare(tmp_path, tart, docker, tool_state)
    assert prepared.returncode == 0, prepared.stderr
    completed = _guard(
        tmp_path,
        "cleanup",
        "--run-id",
        "storage-case",
        "--confirm-run-id",
        "storage-case",
        "--state-root",
        str(tmp_path / "guard-state"),
        env_updates={"FAKE_TOOL_STATE": str(tool_state)},
    )
    assert completed.returncode == 0, completed.stderr

    reused = _prepare(tmp_path, tart, docker, tool_state)

    assert reused.returncode != 0
    assert "unique run ID" in reused.stderr
    assert not (tmp_path / "guard-state" / "active-lease.json").exists()

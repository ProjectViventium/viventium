from __future__ import annotations

import argparse
import hashlib
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
PINNED_SOURCE = "registry.example.invalid/images/macos-vanilla@sha256:" + "a" * 64


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
            print(json.dumps([{"Name": name, "Running": False, "State": "stopped"} for name in names]))
        elif len(sys.argv) == 4 and sys.argv[1] == "clone":
            if "@sha256:" in sys.argv[2] and sys.argv[2] not in names:
                names.append(sys.argv[2])
            names.append(sys.argv[3])
            vms.write_text(json.dumps(names))
            if os.environ.get("FAKE_TART_CLONE_FAIL_AFTER_CREATE") == "1":
                raise SystemExit(2)
        elif len(sys.argv) >= 3 and sys.argv[1] == "run":
            raise SystemExit(int(os.environ.get("FAKE_TART_RUN_EXIT", "0")))
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


@pytest.mark.parametrize("source", ["macos-base", PINNED_SOURCE])
def test_clone_sets_no_auto_prune_and_records_only_the_exact_owned_vm(tmp_path: Path, source: str) -> None:
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
        source,
        env_updates={"FAKE_TOOL_STATE": str(tool_state)},
    )

    assert result.returncode == 0, result.stderr
    events = [
        json.loads(line)
        for line in (tool_state / "tart-events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    clone_event = next(event for event in events if event["argv"][0] == "clone")
    assert clone_event == {
        "argv": ["clone", source, "viventium-qa-storage-case"],
        "no_auto_prune": "1",
    }
    receipt = json.loads(
        (tmp_path / "guard-state" / "runs" / "storage-case.json").read_text(encoding="utf-8")
    )
    assert receipt["phase"] == "VM_READY"
    assert receipt["owned_vm_created"] is True
    assert receipt["source_vm"] == source


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
        replacement = path.with_suffix(".replacement")
        replacement.write_text(json.dumps(payload))
        replacement.replace(path)
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


@pytest.mark.parametrize("source", ["macos-base", PINNED_SOURCE])
def test_cleanup_never_deletes_a_partial_clone_without_created_ownership_proof(
    tmp_path: Path, source: str,
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
        source,
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
    expected = ["viventium-qa-storage-case"] + ([source] if source == PINNED_SOURCE else [])
    assert sorted(json.loads((tool_state / "vms.json").read_text())) == sorted(expected)
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


@pytest.mark.parametrize("source", [
    "registry.example.invalid/images/macos:latest",
    "registry.example.invalid/images/macos",
    "registry.example.invalid/images/macos@sha256:abc",
    "https://registry.example.invalid/images/macos@sha256:" + "a" * 64,
    "user:password@registry.example.invalid/images/macos@sha256:" + "a" * 64,
    "registry.example.invalid/images/../macos@sha256:" + "a" * 64,
    "registry.example.invalid/images//macos@sha256:" + "a" * 64,
    "registry.example.invalid/images/macos:latest@sha256:" + "a" * 64,
    "registry.example.invalid/images/macos@sha256:" + "A" * 64,
    "registry.example.invalid:99999/images/macos@sha256:" + "a" * 64,
    "--insecure",
])
def test_clone_rejects_unpinned_or_ambiguous_source_before_claim(tmp_path: Path, source: str) -> None:
    tart, docker, tool_state = _fake_tools(tmp_path)
    prepared = _prepare(tmp_path, tart, docker, tool_state)
    assert prepared.returncode == 0, prepared.stderr
    result = _guard(tmp_path, "clone", "--run-id", "storage-case", "--state-root",
                    str(tmp_path / "guard-state"), "--source-vm=" + source,
                    env_updates={"FAKE_TOOL_STATE": str(tool_state)})
    assert result.returncode != 0
    receipt = json.loads((tmp_path / "guard-state/runs/storage-case.json").read_text())
    assert receipt["phase"] == "PREPARED" and receipt["owned_vm_intended"] is False
    events = [json.loads(line) for line in (tool_state / "tart-events.jsonl").read_text().splitlines()]
    assert not any(event["argv"][0] == "clone" for event in events)


@pytest.mark.parametrize("preexisting", [True, False])
def test_cleanup_removes_only_introduced_exact_oci_cache(tmp_path: Path, preexisting: bool) -> None:
    tart, docker, tool_state = _fake_tools(tmp_path)
    baseline = ["user-work-vm"] + ([PINNED_SOURCE] if preexisting else [])
    (tool_state / "vms.json").write_text(json.dumps(baseline))
    assert _prepare(tmp_path, tart, docker, tool_state).returncode == 0
    clone = _guard(tmp_path, "clone", "--run-id", "storage-case", "--state-root",
                   str(tmp_path / "guard-state"), "--source-vm", PINNED_SOURCE,
                   env_updates={"FAKE_TOOL_STATE": str(tool_state)})
    assert clone.returncode == 0, clone.stderr
    receipt = json.loads((tmp_path / "guard-state/runs/storage-case.json").read_text())
    assert sorted(receipt["tart_before_clone"]) == sorted(baseline)
    cleanup = _guard(tmp_path, "cleanup", "--run-id", "storage-case", "--confirm-run-id", "storage-case",
                     "--state-root", str(tmp_path / "guard-state"),
                     env_updates={"FAKE_TOOL_STATE": str(tool_state)})
    assert cleanup.returncode == 0, cleanup.stderr
    assert sorted(json.loads((tool_state / "vms.json").read_text())) == sorted(baseline)
    events = [json.loads(line) for line in (tool_state / "tart-events.jsonl").read_text().splitlines()]
    deletes = [event["argv"][1] for event in events if event["argv"][0] == "delete"]
    assert deletes == ["viventium-qa-storage-case"] + ([] if preexisting else [PINNED_SOURCE])


@pytest.mark.parametrize("source", ["macos-base", PINNED_SOURCE])
def test_cleanup_retains_lease_when_recorded_tart_state_and_source_disappear(tmp_path: Path, source: str) -> None:
    tart, docker, tool_state = _fake_tools(tmp_path)
    baseline = ["user-work-vm"]
    (tool_state / "vms.json").write_text(json.dumps(baseline))
    assert _prepare(tmp_path, tart, docker, tool_state).returncode == 0
    assert _guard(tmp_path, "clone", "--run-id", "storage-case", "--state-root",
                  str(tmp_path / "guard-state"), "--source-vm", source,
                  env_updates={"FAKE_TOOL_STATE": str(tool_state)}).returncode == 0
    (tool_state / "vms.json").write_text(json.dumps(["viventium-qa-storage-case"]))
    cleanup = _guard(tmp_path, "cleanup", "--run-id", "storage-case", "--confirm-run-id", "storage-case",
                     "--state-root", str(tmp_path / "guard-state"),
                     env_updates={"FAKE_TOOL_STATE": str(tool_state)})
    assert cleanup.returncode != 0 and "pre-existing Tart state disappeared" in cleanup.stderr
    receipt = json.loads((tmp_path / "guard-state/runs/storage-case.json").read_text())
    assert receipt["tart_before_clone"] == baseline and receipt["phase"] == "CLEANUP_REQUIRED"
    assert (tmp_path / "guard-state/active-lease.json").exists()


def test_cleanup_requires_cache_provenance_and_preserves_other_new_vms(tmp_path: Path) -> None:
    tart, docker, tool_state = _fake_tools(tmp_path)
    assert _prepare(tmp_path, tart, docker, tool_state).returncode == 0
    assert _guard(tmp_path, "clone", "--run-id", "storage-case", "--state-root",
                  str(tmp_path / "guard-state"), "--source-vm", PINNED_SOURCE,
                  env_updates={"FAKE_TOOL_STATE": str(tool_state)}).returncode == 0
    names=json.loads((tool_state / "vms.json").read_text()) + ["new-user-vm"]
    (tool_state / "vms.json").write_text(json.dumps(names))
    cleanup = _guard(tmp_path, "cleanup", "--run-id", "storage-case", "--confirm-run-id", "storage-case",
                     "--state-root", str(tmp_path / "guard-state"),
                     env_updates={"FAKE_TOOL_STATE": str(tool_state)})
    assert cleanup.returncode != 0
    assert "unowned Tart state" in cleanup.stderr
    remaining=json.loads((tool_state / "vms.json").read_text())
    assert PINNED_SOURCE in remaining and "new-user-vm" in remaining


def test_legacy_cleanup_does_not_invent_cache_ownership(tmp_path: Path) -> None:
    tart, docker, tool_state = _fake_tools(tmp_path)
    assert _prepare(tmp_path, tart, docker, tool_state).returncode == 0
    assert _guard(tmp_path, "clone", "--run-id", "storage-case", "--state-root",
                  str(tmp_path / "guard-state"), "--source-vm", PINNED_SOURCE,
                  env_updates={"FAKE_TOOL_STATE": str(tool_state)}).returncode == 0
    path=tmp_path / "guard-state/runs/storage-case.json"
    receipt=json.loads(path.read_text())
    receipt.pop("tart_before_clone", None)
    path.write_text(json.dumps(receipt))
    cleanup = _guard(tmp_path, "cleanup", "--run-id", "storage-case", "--confirm-run-id", "storage-case",
                     "--state-root", str(tmp_path / "guard-state"),
                     env_updates={"FAKE_TOOL_STATE": str(tool_state)})
    assert cleanup.returncode != 0
    assert "pre-clone inventory" in cleanup.stderr
    assert json.loads((tool_state / "vms.json").read_text()) == [PINNED_SOURCE]


def test_introduced_cache_cleanup_refuses_native_gc_with_another_oci_source(tmp_path: Path) -> None:
    tart, docker, tool_state = _fake_tools(tmp_path)
    other = "registry.example.invalid/images/other@sha256:" + "b" * 64
    (tool_state / "vms.json").write_text(json.dumps([other]))
    assert _prepare(tmp_path, tart, docker, tool_state).returncode == 0
    assert _guard(tmp_path, "clone", "--run-id", "storage-case", "--state-root",
                  str(tmp_path / "guard-state"), "--source-vm", PINNED_SOURCE,
                  env_updates={"FAKE_TOOL_STATE": str(tool_state)}).returncode == 0
    cleanup = _guard(tmp_path, "cleanup", "--run-id", "storage-case", "--confirm-run-id", "storage-case",
                     "--state-root", str(tmp_path / "guard-state"),
                     env_updates={"FAKE_TOOL_STATE": str(tool_state)})
    assert cleanup.returncode != 0 and "shared OCI cache" in cleanup.stderr
    assert sorted(json.loads((tool_state / "vms.json").read_text())) == sorted([other, PINNED_SOURCE])


@pytest.mark.parametrize("failure", [None, "extra-container", "volume", "evidence", "wrong-run"])
def test_cleanup_acknowledges_only_exact_authorized_external_runtime_changes(tmp_path: Path, failure: str | None) -> None:
    tart, docker, tool_state = _fake_tools(tmp_path)
    state_path = tool_state / "docker.json"
    original = json.loads(state_path.read_text())
    original["containers"] = ["a" * 64, "b" * 64]
    state_path.write_text(json.dumps(original))
    assert _prepare(tmp_path, tart, docker, tool_state).returncode == 0
    receipt_path = tmp_path / "guard-state/runs/storage-case.json"
    baseline = json.loads(receipt_path.read_text())["docker_baseline"]
    current = dict(original, containers=["b" * 64, "c" * 64])
    state_path.write_text(json.dumps(current))
    common = ("cleanup", "--run-id", "storage-case", "--confirm-run-id", "storage-case",
              "--state-root", str(tmp_path / "guard-state"))
    rejected = _guard(tmp_path, *common, env_updates={"FAKE_TOOL_STATE": str(tool_state)})
    assert rejected.returncode != 0 and "disappeared" in rejected.stderr
    evidence = tmp_path / "authorized-stop.log"
    evidence.write_text("Supported isolated runtime stop and restart completed\n")
    acknowledgement = {"schema_version": 1, "run_id": "storage-case", "reason": "Operator authorized concurrent isolated runtime restart",
        "removed_containers": ["a" * 64], "added_containers": ["c" * 64], "removed_images": [], "added_images": [],
        "evidence": [{"path": str(evidence), "sha256": hashlib.sha256(evidence.read_bytes()).hexdigest()}]}
    if failure == "extra-container":
        current["containers"].append("d" * 64)
    elif failure == "volume":
        current["volumes"] = []
    elif failure == "evidence":
        evidence.write_text("Changed after review")
    elif failure == "wrong-run":
        acknowledgement["run_id"] = "another-run"
    state_path.write_text(json.dumps(current))
    proof = tmp_path / "authorized-external-change.json"
    proof.write_text(json.dumps(acknowledgement))
    proof.chmod(0o600)
    result = _guard(tmp_path, *common, "--acknowledge-external-runtime-changes", str(proof),
                    env_updates={"FAKE_TOOL_STATE": str(tool_state)})
    receipt = json.loads(receipt_path.read_text())
    assert receipt["docker_baseline"] == baseline
    assert json.loads(state_path.read_text()) == current
    if failure:
        assert result.returncode != 0
        assert (tmp_path / "guard-state/active-lease.json").exists()
    else:
        assert result.returncode == 0, result.stderr
        assert receipt["phase"] == "COMPLETE_WITH_AUTHORIZED_EXTERNAL_CHANGE"
        assert receipt["authorized_external_runtime_changes"]["record"] == acknowledgement
        assert not (tmp_path / "guard-state/active-lease.json").exists()


def test_cleanup_rechecks_docker_after_external_evidence_validation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tart, docker, tool_state = _fake_tools(tmp_path)
    state_path = tool_state / "docker.json"
    state = json.loads(state_path.read_text())
    state["containers"] = ["a" * 64]
    state_path.write_text(json.dumps(state))
    assert _prepare(tmp_path, tart, docker, tool_state).returncode == 0
    state["containers"] = []
    state_path.write_text(json.dumps(state))
    evidence = tmp_path / "authorized-stop.log"
    evidence.write_text("Supported isolated runtime stop completed\n")
    record = {"schema_version": 1, "run_id": "storage-case", "reason": "Authorized isolated runtime stop",
              "removed_containers": ["a" * 64], "added_containers": [], "removed_images": [], "added_images": [],
              "evidence": [{"path": str(evidence), "sha256": hashlib.sha256(evidence.read_bytes()).hexdigest()}]}
    proof = tmp_path / "authorized-stop.json"
    proof.write_text(json.dumps(record)); proof.chmod(0o600)
    module = _load_guard_module()
    validate = module._authorized_external_runtime_changes
    def validate_then_change(*args: object) -> object:
        acknowledgement = validate(*args)
        state["volumes"] = []
        state_path.write_text(json.dumps(state))
        return acknowledgement
    monkeypatch.setenv("FAKE_TOOL_STATE", str(tool_state))
    monkeypatch.setattr(module, "_authorized_external_runtime_changes", validate_then_change)
    result = module.main(["cleanup", "--run-id", "storage-case", "--confirm-run-id", "storage-case",
                          "--state-root", str(tmp_path / "guard-state"),
                          "--acknowledge-external-runtime-changes", str(proof)])
    assert result != 0
    receipt = json.loads((tmp_path / "guard-state/runs/storage-case.json").read_text())
    assert receipt["phase"] == "CLEANUP_REQUIRED" and "volume disappeared" in receipt["detail"]
    assert (tmp_path / "guard-state/active-lease.json").exists()


@pytest.mark.parametrize("failure", [None, "unlisted-image", "volume"])
def test_cleanup_acknowledges_only_exact_authorized_image_rebuild(tmp_path: Path, failure: str | None) -> None:
    tart, docker, tool_state = _fake_tools(tmp_path)
    state_path = tool_state / "docker.json"
    state = json.loads(state_path.read_text())
    old_image, new_image = "sha256:" + "d" * 64, "sha256:" + "e" * 64
    state["images"] = [old_image]
    state_path.write_text(json.dumps(state))
    assert _prepare(tmp_path, tart, docker, tool_state).returncode == 0
    receipt_path = tmp_path / "guard-state/runs/storage-case.json"
    baseline = json.loads(receipt_path.read_text())["docker_baseline"]
    state["images"] = [new_image]
    if failure == "unlisted-image":
        state["images"].append("sha256:" + "f" * 64)
    elif failure == "volume":
        state["volumes"] = []
    state_path.write_text(json.dumps(state))
    evidence = tmp_path / "supported-rebuild.json"
    evidence.write_text(json.dumps({"oldIndex":old_image,"newIndex":new_image,"runtimeManifestUnchanged":True}))
    acknowledgement = {"schema_version":1,"run_id":"storage-case","reason":"Operator-authorized runtime rebuild; exact native build records reviewed",
        "removed_containers":[],"added_containers":[],"removed_images":[old_image],"added_images":[new_image],
        "evidence":[{"path":str(evidence),"sha256":hashlib.sha256(evidence.read_bytes()).hexdigest()}]}
    proof=tmp_path / "authorized-rebuild.json"
    proof.write_text(json.dumps(acknowledgement));proof.chmod(0o600)
    result = _guard(tmp_path,"cleanup","--run-id","storage-case","--confirm-run-id","storage-case",
        "--state-root",str(tmp_path / "guard-state"),"--acknowledge-external-runtime-changes",str(proof),
        env_updates={"FAKE_TOOL_STATE":str(tool_state)})
    receipt=json.loads(receipt_path.read_text())
    assert receipt["docker_baseline"] == baseline
    assert json.loads(state_path.read_text()) == state
    if failure:
        assert result.returncode != 0 and (tmp_path / "guard-state/active-lease.json").exists()
    else:
        assert result.returncode == 0, result.stderr
        assert receipt["phase"] == "COMPLETE_WITH_AUTHORIZED_EXTERNAL_CHANGE"
        assert receipt["authorized_external_runtime_changes"]["record"] == acknowledgement


@pytest.mark.parametrize("failure", [None, "extra-container", "volume", "evidence", "wrong-run", "disk-replaced", "foreign-vm", "growth"])
def test_guarded_run_accepts_only_exact_reviewed_external_delta_and_retains_vm(tmp_path: Path, failure: str | None) -> None:
    tart, docker, tool_state = _fake_tools(tmp_path)
    state_path = tool_state / "docker.json"
    original = json.loads(state_path.read_text())
    original["containers"] = ["a" * 64, "b" * 64]
    state_path.write_text(json.dumps(original))
    policy = _policy(tmp_path, minimum_free_bytes_before_run=1, abort_below_free_bytes=1,
                     max_docker_logical_growth_from_clean_baseline_bytes=1024 if failure == "growth" else 2**36,
                     sample_interval_seconds=0.01)
    assert _prepare(tmp_path, tart, docker, tool_state, policy=policy).returncode == 0
    assert _guard(tmp_path, "clone", "--run-id", "storage-case", "--state-root", str(tmp_path / "guard-state"),
                  "--source-vm", "macos-base", env_updates={"FAKE_TOOL_STATE": str(tool_state)}).returncode == 0
    receipt_path = tmp_path / "guard-state/runs/storage-case.json"
    before = json.loads(receipt_path.read_text())
    current = dict(original, containers=["b" * 64, "c" * 64])
    evidence = tmp_path / "reviewed-restart.log"
    evidence.write_text("The separate runtime owner completed its authorized restart\n")
    record = {"schema_version": 1, "run_id": "storage-case", "reason": "Reviewed concurrent runtime restart",
              "removed_containers": ["a" * 64], "added_containers": ["c" * 64], "removed_images": [], "added_images": [],
              "evidence": [{"path": str(evidence), "sha256": hashlib.sha256(evidence.read_bytes()).hexdigest()}]}
    if failure == "extra-container": current["containers"].append("d" * 64)
    elif failure == "volume": current["volumes"] = []
    elif failure == "evidence": evidence.write_text("Unreviewed replacement")
    elif failure == "wrong-run": record["run_id"] = "another-run"
    elif failure == "disk-replaced":
        (tmp_path / "Docker.raw").rename(tmp_path / "original-disk")
        (tmp_path / "Docker.raw").touch()
    elif failure == "foreign-vm": (tool_state / "vms.json").write_text(json.dumps(["viventium-qa-another-run"]))
    elif failure == "growth":
        with (tmp_path / "Docker.raw").open("r+b") as handle: handle.truncate(4096)
    state_path.write_text(json.dumps(current))
    proof = tmp_path / "reviewed-external-change.json"
    proof.write_text(json.dumps(record)); proof.chmod(0o600)
    marker = tmp_path / "command-ran"
    driver = tmp_path / "qa-driver"
    _write_executable(driver, "#!/usr/bin/env python3\nfrom pathlib import Path\nimport sys\nPath(sys.argv[1]).touch()\n")
    result = _guard(tmp_path, "run", "--run-id", "storage-case", "--state-root", str(tmp_path / "guard-state"),
                    "--acknowledge-external-runtime-changes", str(proof), "--", str(driver), str(marker),
                    env_updates={"FAKE_TOOL_STATE": str(tool_state)})
    after = json.loads(receipt_path.read_text())
    assert after["docker_baseline"] == before["docker_baseline"]
    assert after["host_free_bytes_at_prepare"] == before["host_free_bytes_at_prepare"]
    assert after["policy"] == before["policy"]
    assert (tmp_path / "guard-state/active-lease.json").exists()
    assert json.loads(state_path.read_text()) == current
    events = [json.loads(line)["argv"][0] for line in (tool_state / "tart-events.jsonl").read_text().splitlines()]
    assert "delete" not in events and events.count("clone") == 1
    if failure:
        assert result.returncode != 0 and not marker.exists()
        assert after == before
    else:
        assert result.returncode == 0, result.stderr
        assert marker.exists() and after["phase"] == "RUN_COMPLETE"
        assert after["external_runtime_change_acknowledgements"][0]["record"] == record
        # Prior acknowledgement is evidence, not an implicit exemption for later commands.
        later = _guard(tmp_path, "run", "--run-id", "storage-case", "--state-root", str(tmp_path / "guard-state"),
                       "--", str(driver), str(marker), env_updates={"FAKE_TOOL_STATE": str(tool_state)})
        assert later.returncode != 0 and "disappeared" in later.stderr


def test_guarded_run_rechecks_acknowledged_delta_during_command(tmp_path: Path) -> None:
    module = _load_guard_module()
    disk = {"exists": True, "device": 1, "inode": 2, "logical_bytes": 10, "physical_bytes": 10}
    baseline = {"context": "desktop-linux", "containers": ["a" * 64], "images": [], "volumes": ["retained"], "disk": disk}
    current = dict(baseline, containers=["b" * 64])
    delta = {"removed_containers": ["a" * 64], "added_containers": ["b" * 64], "removed_images": [], "added_images": []}
    receipt = {"candidate": str(tmp_path), "docker": "synthetic", "docker_disk": "synthetic", "docker_baseline": baseline}
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(module, "_docker_baseline", lambda *args: current)
        assert module._sample(receipt, external_runtime_changes=delta)[0] == current
        current["containers"].append("c" * 64)
        with pytest.raises(module.GuardError, match="exactly match"):
            module._sample(receipt, external_runtime_changes=delta)


def test_stopped_vm_recovery_preserves_failed_run_and_original_guards(tmp_path: Path) -> None:
    tart, docker, tool_state = _fake_tools(tmp_path)
    prepared = _prepare(tmp_path, tart, docker, tool_state)
    assert prepared.returncode == 0, prepared.stderr
    env = {"FAKE_TOOL_STATE": str(tool_state)}
    clone = _guard(tmp_path, "clone", "--run-id", "storage-case", "--state-root", str(tmp_path / "guard-state"), "--source-vm", PINNED_SOURCE, env_updates=env)
    assert clone.returncode == 0, clone.stderr
    args = ("run", "--run-id", "storage-case", "--state-root", str(tmp_path / "guard-state"))
    command = (str(tart), "run", "viventium-qa-storage-case")
    failed = _guard(tmp_path, *args, "--", *command, env_updates=dict(env, FAKE_TART_RUN_EXIT="2"))
    assert failed.returncode != 0
    path = tmp_path / "guard-state/runs/storage-case.json"
    before = json.loads(path.read_text())
    assert before["phase"] == "CLEANUP_REQUIRED"
    blocked = _guard(tmp_path, *args, "--", *command, env_updates=env)
    assert blocked.returncode != 0 and json.loads(path.read_text()) == before
    result = _guard(tmp_path, *args, "--resume-stopped-vm", "--", *command, env_updates=env)
    assert result.returncode == 0, result.stderr
    after = json.loads(path.read_text())
    for key in ("docker_baseline", "host_free_bytes_at_prepare", "policy", "created_unix_seconds", "source_vm"):
        assert after[key] == before[key]
    recovery = after["stopped_vm_recoveries"][-1]
    assert recovery["previous_detail"] == before["detail"]
    assert recovery["previous_guarded_process"] == before["last_guarded_process"]
    assert after["phase"] == "RUN_COMPLETE" and (tmp_path / "guard-state/active-lease.json").exists()
    events = [json.loads(line)["argv"][0] for line in (tool_state / "tart-events.jsonl").read_text().splitlines()]
    assert events.count("clone") == 1 and "delete" not in events


@pytest.mark.parametrize("failure", [None, "running", "unknown-state", "foreign-vm", "live-tart", "live-vm", "live-group", "wrong-driver", "new-capability"])
def test_stopped_vm_recovery_requires_current_owner_absence(tmp_path: Path, monkeypatch, failure: str | None) -> None:
    module = _load_guard_module()
    vm = "viventium-qa-storage-case"
    receipt = {"owned_vm_created": True, "tart": "/synthetic/tart", "vm_name": vm,
               "policy": {"qa_vm_prefix": "viventium-qa-"}}
    argv = [receipt["tart"], "run", vm]
    inventory = [{"Name": vm, "Running": False, "State": "stopped"}]
    processes = ""
    if failure == "running": inventory[0]["Running"] = True
    if failure == "unknown-state": del inventory[0]["State"]
    if failure == "foreign-vm": inventory.append({"Name": "viventium-qa-other", "Running": False, "State": "stopped"})
    if failure == "live-tart": processes = "888888 1 888888 /synthetic/tart /synthetic/tart run other"
    if failure == "live-vm": processes = "888888 1 888888 /synthetic/driver /synthetic/driver " + vm
    if failure == "live-group": receipt["last_guarded_process"] = {"pid": 888888, "argv": argv}
    if failure == "wrong-driver": argv[0] = "/synthetic/driver"
    if failure == "new-capability": argv.insert(2, "--dir=host-data")
    monkeypatch.setattr(module, "_process_group_present", lambda pid: True)
    monkeypatch.setattr(module, "_run_read_only", lambda args: processes if args[0] == "/bin/ps" else json.dumps(inventory))
    if failure:
        with pytest.raises(module.GuardError): module._assert_stopped_vm_recovery(receipt, argv)
    else:
        module._assert_stopped_vm_recovery(receipt, argv)


def test_stopped_vm_recovery_keeps_storage_failure_closed(tmp_path: Path, monkeypatch) -> None:
    module = _load_guard_module()
    receipt = {"phase": "CLEANUP_REQUIRED", "detail": "original failure"}
    before = dict(receipt)
    monkeypatch.setattr(module, "_load_receipt", lambda *args: receipt)
    monkeypatch.setattr(module, "_assert_stopped_vm_recovery", lambda *args: None)
    monkeypatch.setattr(module, "_safety_violation", lambda *args, **kwargs: "host physical growth exceeded the guarded QA budget")
    monkeypatch.setattr(module, "_run_monitored", lambda *args, **kwargs: pytest.fail("unsafe command started"))
    args = argparse.Namespace(state_root=str(tmp_path / "guard"), run_id="case", resume_stopped_vm=True,
        acknowledge_external_runtime_changes=None, argv=["/synthetic/tart", "run", "viventium-qa-case"])
    with pytest.raises(module.GuardError, match="growth exceeded"):
        module.command_run(args)
    assert receipt == before


@pytest.mark.parametrize("violation", [None, "floor", "docker", "growth"])
def test_host_growth_amendment_retains_other_limits_and_original_policy(tmp_path: Path, monkeypatch, violation: str | None) -> None:
    module = _load_guard_module()
    gib = 2 ** 30
    policy = json.loads(POLICY.read_text())
    receipt = {"policy": policy, "host_free_bytes_at_prepare": 108 * gib,
               "docker_baseline": {"disk": {"physical_bytes": 0, "logical_bytes": 0}}}
    free = (59 if violation == "floor" else 67 if violation == "growth" else 73) * gib
    docker = {"disk": {"physical_bytes": 17 * gib if violation == "docker" else 0, "logical_bytes": 0}}
    monkeypatch.setattr(module, "_sample", lambda *args, **kwargs: (docker, free))
    assert module._safety_violation(receipt) is not None
    actual = module._safety_violation(receipt, host_growth_budget_bytes=40 * gib)
    assert (actual is None) == (violation is None)
    if violation == "floor": assert "free-space floor" in actual
    if violation == "docker": assert "Docker physical" in actual
    if violation == "growth": assert "host physical" in actual
    assert receipt["policy"] == policy
    assert policy["max_host_physical_growth_bytes"] == 32 * gib
    assert module._safety_violation(receipt) is not None


@pytest.mark.parametrize("budget_gib,floor_gib,growth_gib", [(40, None, 35), (72, 40, 54)])
def test_host_growth_amendment_is_recorded_without_resetting_failed_baseline(tmp_path: Path, monkeypatch, budget_gib, floor_gib, growth_gib) -> None:
    module = _load_guard_module()
    tart, docker, tool_state = _fake_tools(tmp_path)
    assert _prepare(tmp_path, tart, docker, tool_state).returncode == 0
    env = {"FAKE_TOOL_STATE": str(tool_state)}
    assert _guard(tmp_path, "clone", "--run-id", "storage-case", "--state-root", str(tmp_path / "guard-state"), "--source-vm", PINNED_SOURCE, env_updates=env).returncode == 0
    failed = _guard(tmp_path, "run", "--run-id", "storage-case", "--state-root", str(tmp_path / "guard-state"), "--", str(tart), "run", "viventium-qa-storage-case", env_updates=dict(env, FAKE_TART_RUN_EXIT="2"))
    assert failed.returncode != 0
    path = tmp_path / "guard-state/runs/storage-case.json"
    before = json.loads(path.read_text())
    monkeypatch.setenv("FAKE_TOOL_STATE", str(tool_state))
    gib = 2 ** 30
    before["host_free_bytes_at_prepare"] = 108*gib
    before["policy"]["abort_below_free_bytes"] = 60*gib
    path.write_text(json.dumps(before))
    monkeypatch.setattr(module, "_sample", lambda *args, **kwargs: (before["docker_baseline"], before["host_free_bytes_at_prepare"] - growth_gib * gib))
    observed = []
    def run(receipt, argv, **options):
        observed.append(options)
        assert receipt["policy"] == before["policy"]
        return 0, None
    monkeypatch.setattr(module, "_run_monitored", run)
    floor_args = ["--minimum-host-free-bytes", str(floor_gib*gib)] if floor_gib is not None else []
    args = module.build_parser().parse_args(["run", "--run-id", "storage-case", "--state-root", str(tmp_path / "guard-state"), "--resume-stopped-vm", "--host-growth-budget-bytes", str(budget_gib*gib), *floor_args, "--resource-budget-reason", "Finish the same retained installation", "--", str(tart), "run", "viventium-qa-storage-case"])
    module.command_run(args)
    after = json.loads(path.read_text())
    for key in ("policy", "docker_baseline", "host_free_bytes_at_prepare", "created_unix_seconds", "source_vm"):
        assert after[key] == before[key]
    amendment = after["resource_budget_amendments"][-1]
    assert amendment["original_policy"] == before["policy"]
    expected_policy = {**before["policy"], "max_host_physical_growth_bytes": budget_gib*gib}
    expected_options = {"host_growth_budget_bytes": budget_gib*gib}
    if floor_gib is not None:
        expected_policy["abort_below_free_bytes"] = floor_gib*gib
        expected_options["minimum_host_free_bytes"] = floor_gib*gib
    assert amendment["effective_policy"] == expected_policy
    assert after["stopped_vm_recoveries"][-1]["previous_detail"] == before["detail"]
    assert observed == [expected_options]
    assert module._safety_violation(after) is not None


@pytest.mark.parametrize("budget,reason", [(None, "reason"), (0, "reason"), (1, None), (1, " ")])
def test_host_growth_amendment_requires_explicit_valid_budget_and_reason(tmp_path: Path, monkeypatch, budget, reason) -> None:
    module = _load_guard_module()
    receipt = {"phase": "CLEANUP_REQUIRED"}
    monkeypatch.setattr(module, "_load_receipt", lambda *args: receipt)
    monkeypatch.setattr(module, "_assert_stopped_vm_recovery", lambda *args: pytest.fail("invalid allowance reached process checks"))
    args = argparse.Namespace(state_root=str(tmp_path / "state"), run_id="case", resume_stopped_vm=True,
        host_growth_budget_bytes=budget, resource_budget_reason=reason, argv=["/synthetic/tart", "run", "viventium-qa-case"])
    with pytest.raises(module.GuardError): module.command_run(args)
    assert receipt == {"phase": "CLEANUP_REQUIRED"}


def test_host_growth_amendment_is_enforced_throughout_actual_child_run(tmp_path: Path, monkeypatch) -> None:
    module = _load_guard_module()
    gib = 2 ** 30
    policy = json.loads(POLICY.read_text()); policy["sample_interval_seconds"] = 0.01
    receipt = {"policy": policy, "host_free_bytes_at_prepare": 108*gib,
               "docker_baseline": {"disk": {"physical_bytes": 0, "logical_bytes": 0}}}
    observed = []
    def sample(*args, **kwargs):
        observed.append(True)
        return receipt["docker_baseline"], (73 if len(observed) == 1 else 67)*gib
    monkeypatch.setattr(module, "_sample", sample)
    status, violation = module._run_monitored(receipt, [sys.executable, "-c", "import time; time.sleep(30)"], host_growth_budget_bytes=40*gib)
    assert status != 0 and violation == "host physical growth exceeded the guarded QA budget"
    assert len(observed) == 2
    assert module._process_group_present(receipt["last_guarded_process"]["pid"]) is False


@pytest.mark.parametrize("free_gib,expected", [(41, None), (39, "free-space floor")])
def test_free_floor_amendment_retains_original_floor(tmp_path: Path, monkeypatch, free_gib, expected) -> None:
    module = _load_guard_module()
    gib = 2 ** 30
    policy = json.loads(POLICY.read_text())
    receipt = {"policy": policy, "host_free_bytes_at_prepare": 108*gib,
               "docker_baseline": {"disk": {"physical_bytes": 0, "logical_bytes": 0}}}
    monkeypatch.setattr(module, "_sample", lambda *args, **kwargs: (receipt["docker_baseline"], free_gib*gib))
    actual = module._safety_violation(receipt, host_growth_budget_bytes=72*gib, minimum_host_free_bytes=40*gib)
    assert actual is None if expected is None else expected in actual
    assert policy["abort_below_free_bytes"] == 60*gib
    assert "free-space floor" in module._safety_violation(receipt, host_growth_budget_bytes=72*gib)


@pytest.mark.parametrize("floor,reason", [(31*2**30, "reason"), (0, "reason"), (True, "reason"), (40*2**30, None)])
def test_free_floor_amendment_requires_minimum_and_reason(tmp_path: Path, monkeypatch, floor, reason) -> None:
    module = _load_guard_module()
    receipt = {"phase": "CLEANUP_REQUIRED"}
    monkeypatch.setattr(module, "_load_receipt", lambda *args: receipt)
    monkeypatch.setattr(module, "_assert_stopped_vm_recovery", lambda *args: pytest.fail("invalid floor reached process checks"))
    args = argparse.Namespace(state_root=str(tmp_path / "state"), run_id="case", resume_stopped_vm=True,
        minimum_host_free_bytes=floor, resource_budget_reason=reason, argv=["/synthetic/tart", "run", "viventium-qa-case"])
    with pytest.raises(module.GuardError): module.command_run(args)
    assert receipt == {"phase": "CLEANUP_REQUIRED"}


def test_free_floor_amendment_is_enforced_during_child_run(tmp_path: Path, monkeypatch) -> None:
    module = _load_guard_module()
    gib = 2 ** 30
    policy = json.loads(POLICY.read_text()); policy["sample_interval_seconds"] = 0.01
    receipt = {"policy": policy, "host_free_bytes_at_prepare": 108*gib,
               "docker_baseline": {"disk": {"physical_bytes": 0, "logical_bytes": 0}}}
    observed = []
    def sample(*args, **kwargs):
        observed.append(True)
        return receipt["docker_baseline"], (41 if len(observed) == 1 else 39)*gib
    monkeypatch.setattr(module, "_sample", sample)
    status, violation = module._run_monitored(receipt, [sys.executable, "-c", "import time; time.sleep(30)"],
        host_growth_budget_bytes=72*gib, minimum_host_free_bytes=40*gib)
    assert status != 0 and violation == "free-space floor reached during guarded QA"
    assert len(observed) == 2
    assert module._process_group_present(receipt["last_guarded_process"]["pid"]) is False


@pytest.mark.parametrize("option,allowed", [("--capture-system-keys", True), ("--vnc", False), ("--dir=host-data", False), ("--net-bridged=en0", False)])
def test_stopped_guest_input_capture_keeps_access_boundaries(monkeypatch, option: str, allowed: bool) -> None:
    module = _load_guard_module()
    vm = "viventium-qa-input-case"
    receipt = {"owned_vm_created": True, "tart": "/synthetic/tart", "vm_name": vm,
               "policy": {"qa_vm_prefix": "viventium-qa-"}}
    inventory = [{"Name": vm, "Running": False, "State": "stopped"}]
    monkeypatch.setattr(module, "_run_read_only", lambda args: "" if args[0] == "/bin/ps" else json.dumps(inventory))
    argv = [receipt["tart"], "run", "--no-audio", "--no-clipboard", option, vm]
    if allowed:
        module._assert_stopped_vm_recovery(receipt, argv)
    else:
        with pytest.raises(module.GuardError):
            module._assert_stopped_vm_recovery(receipt, argv)


@pytest.mark.parametrize("failure", [None, "writable", "extra", "symlink", "hardlink", "tamper", "rw", "broader", "stable"])
def test_retained_vm_share_accepts_only_sealed_verified_qa_artifacts(tmp_path, monkeypatch, failure):
    module = _load_guard_module()
    spec = importlib.util.spec_from_file_location("native_payload_test_helpers", ROOT / "tests/release/test_native_payload.py")
    helpers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helpers)
    monkeypatch.syspath_prepend(str(ROOT / "scripts/viventium"))
    shared = tmp_path / "artifacts"
    shared.mkdir()
    manifest, archive, payload = helpers.write_candidate(shared)
    import native_payload
    # This synthetic macOS archive is verified on Linux CI too. Keep real payload
    # verification, but declare its test host version instead of probing sw_vers.
    monkeypatch.setattr(
        native_payload.platform, "mac_ver",
        lambda: (payload["platform"]["minimum_version"], ("", "", ""), ""),
    )
    if failure == "extra": (shared / "private.txt").write_text("not an artifact")
    if failure == "symlink":
        original = tmp_path / "original.zip"
        archive.rename(original)
        archive.symlink_to(original)
    if failure == "hardlink": os.link(archive, tmp_path / "linked.zip")
    if failure == "tamper": archive.write_bytes(b"tampered")
    if failure == "stable":
        payload.update(channel="stable", local_qa=False)
        manifest.write_bytes(helpers.load_module().canonical_manifest_bytes(payload))
    for entry in shared.iterdir():
        if not entry.is_symlink(): entry.chmod(0o444)
    shared.chmod(0o555)
    if failure == "writable": archive.chmod(0o644)
    option = f"--dir=payload:{shared.resolve()}:ro"
    if failure == "rw": option = option[:-2] + "rw"
    if failure == "broader": option = f"--dir=payload:{tmp_path.resolve()}:ro"
    vm = "viventium-qa-share"
    receipt = {"owned_vm_created": True, "tart": "/synthetic/tart", "vm_name": vm,
               "policy": {"qa_vm_prefix": "viventium-qa-"}}
    inventory = [{"Name": vm, "Running": False, "State": "stopped"}]
    monkeypatch.setattr(module, "_run_read_only", lambda args: "" if args[0] == "/bin/ps" else json.dumps(inventory))
    argv = [receipt["tart"], "run", option, vm]
    try:
        if failure:
            with pytest.raises(module.GuardError): module._assert_stopped_vm_recovery(receipt, argv)
            assert "read_only_artifact_transports" not in receipt
        else:
            module._assert_stopped_vm_recovery(receipt, argv)
            proof = receipt["read_only_artifact_transports"][-1]
            assert proof["archive_sha256"] == payload["artifact"]["sha256"]
            assert proof["manifest_sha256"] == helpers.sha256(manifest.read_bytes())
            assert proof["directory"] == str(shared.resolve()) and proof["read_only"] is True
            assert proof["argv"] == argv
    finally:
        shared.chmod(0o755)

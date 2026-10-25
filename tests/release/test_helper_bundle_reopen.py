"""Bundle recovery reuses the helper's native owner without opening a second GUI process."""
from __future__ import annotations

import json
import os
import plistlib
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
INSTALLER = ROOT / "scripts/viventium/install_macos_helper.sh"


def shell_function(source: str, name: str) -> str:
    match = re.search(r"^" + re.escape(name) + r"\(\) \{\n", source, re.MULTILINE)
    if match is None:
        return ""
    tail = source[match.start():]
    next_function = re.search(r"\n[A-Za-z_][A-Za-z_0-9]*\(\) \{\n", tail)
    end = next_function.start() if next_function is not None else tail.index('\ncase "$MODE" in')
    return tail[:end] + "\n"


def recovery_bundle_branch(source: str) -> str:
    return source.split('    if [[ "$RECOVERY_BUNDLE_ONLY" == "1" ]]; then\n', 1)[1].split(
        "    fi\n    select_helper_agent_path", 1,
    )[0]


@pytest.fixture
def recovery_run(tmp_path: Path):
    source = INSTALLER.read_text()
    branch = recovery_bundle_branch(source)
    tail = branch.split("      commit_install_transaction\n", 1)[1].split("      exit 0\n", 1)[0]
    functions = "".join(shell_function(source, name) for name in (
        "verify_helper_supervisor_binding", "pause_recovery_helper_supervisor",
        "restore_recovery_helper_supervisor", "reopen_recovery_helper",
        "rollback_install_transaction", "activate_staged_bundle", "commit_install_transaction",
        "bootstrap_launch_agent", "launch_helper_app",
    ))
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir(mode=0o700)
    support = tmp_path / "support"
    support.mkdir(mode=0o700)
    repo = tmp_path / "repository"
    repo.mkdir(mode=0o700)
    bundle = tmp_path / "Applications/Viventium.app"
    executable = bundle / "Contents/MacOS/ViventiumHelper"
    executable.parent.mkdir(parents=True, mode=0o700)
    executable.write_text("synthetic helper fixture\n")
    executable.chmod(0o700)
    config = support / "helper-config.json"
    config.write_text(json.dumps({"repoRoot": str(repo), "appSupportDir": str(support),
                                  "runtimeSupervision": {"desiredState": "running"},
                                  "preserveFixture": True}))
    config.chmod(0o600)
    original_config = config.read_bytes()
    persistent_plist = support / "persistent.plist"
    session_plist = support / "runtime/helper-supervisor.plist"
    session_plist.parent.mkdir(mode=0o700)
    for path in (persistent_plist, session_plist):
        path.write_bytes(plistlib.dumps({"Label": "ai.viventium.helper", "ProgramArguments": [str(executable)]}))
        path.chmod(0o600)
    state_path = tmp_path / "fixture-state.json"

    fixture_script = "#!" + sys.executable + "\n" + r'''
import json, os, sys
from pathlib import Path
path = Path(os.environ["FIXTURE_STATE"])
state = json.loads(path.read_text())
tool = Path(sys.argv[0]).name
args = sys.argv[1:]
state["calls"].append([tool, *args])
status = 0
if tool == "launchctl":
    if args[0] in {"print", "kickstart", "bootout"} and args[-1] != f"gui/{os.getuid()}/ai.viventium.helper":
        raise SystemExit("Recovery targeted another native owner")
    if args[0] == "print":
        if state["pending_unload_checks"]:
            state["pending_unload_checks"] -= 1
            if not state["pending_unload_checks"]:
                state["loaded"] = False
                state["helpers"] = 0
                state["mapped_generations"] = []
        if state["loaded"]:
            print("path = " + state["job_path"])
            print("program = " + state["program"])
        else:
            status = 113
    elif args[0] == "kickstart":
        state["kickstarts"].append(args)
        if "-k" in args and not state["allow_forced_kickstart"]:
            status = 90
        elif not state["loaded"]:
            status = 113
        elif not state["helpers"]:
            state["helpers"] = 1
            state["mapped_generations"] = [state["bundle_generation"]]
        if state["pending_unload_checks"]:
            # A queued bootout can finish after a kickstart accepted against the still-visible job.
            state["pending_unload_checks"] = 0
            state["loaded"] = False
            state["helpers"] = 0
            state["mapped_generations"] = []
    elif args[0] == "bootout":
        if len(args) != 2:
            raise SystemExit("Recovery must boot out the exact validated job")
        if state["bootout_delayed_failure"]:
            state["pending_unload_checks"] = 5
            status = 36
        elif state["bootout_refused"]:
            status = 36
        else:
            state["loaded"] = False
            state["helpers"] = 0
            state["mapped_generations"] = []
            if state["bootout_unloaded_failure"]:
                status = 36
    elif args[0] == "bootstrap":
        if state["loaded"] or args[1] != f"gui/{os.getuid()}" or args[2] != state["job_path"]:
            raise SystemExit("Recovery must restore its exact prior job")
        state["bootstrap_paths"].append(args[2])
        state["loaded"] = True
        state["helpers"] = 1
        state["mapped_generations"] = [state["bundle_generation"]]
    else:
        raise SystemExit("Unexpected launchctl mutation in recovery-only reopen")
elif tool == "pgrep":
    if state["helpers"]:
        print("4242")
    else:
        status = 1
elif tool == "open_fixture":
    if args != ["-g", os.environ["FIXTURE_BUNDLE"]]:
        raise SystemExit("Unexpected application open")
    state["opens"] += 1
    state["helpers"] += 1
    state["mapped_generations"].append(state["bundle_generation"])
elif tool == "fixture_effect":
    state["effects"].append(args[0])
    if args[0] == "stop_existing_helper":
        state["helpers"] = 0
        state["mapped_generations"] = []
        if state["loaded"]:
            # A live KeepAlive job can respawn before the staged bundle is activated.
            state["helpers"] = 1
            state["mapped_generations"] = [state["bundle_generation"]]
elif tool == "fixture_exit_state":
    state["supervisor_restore_flag"] = int(args[0])
    if state["pending_unload_checks"]:
        state["pending_unload_checks"] = 0
        state["loaded"] = False
        state["helpers"] = 0
        state["mapped_generations"] = []
elif tool == "transaction_fixture":
    action = args[1]
    state["effects"].append("transaction:" + action)
    if action == "activate":
        state["bundle_generation"] = "new"
        if state["fail_activation"]:
            status = 42
    elif action == "rollback-persisted":
        if state["fail_rollback"]:
            status = 43
        else:
            state["bundle_generation"] = "old"
    elif action != "commit-persisted":
        raise SystemExit("Unexpected helper transaction")
else:
    raise SystemExit("Unexpected fixture command")
state["timeline"].append({"tool": tool, "args": args, "loaded": state["loaded"],
    "bundle": state["bundle_generation"], "mapped": state["mapped_generations"][:]})
path.write_text(json.dumps(state))
raise SystemExit(status)
'''
    for command in ("launchctl", "pgrep", "open_fixture", "fixture_effect", "fixture_exit_state", "transaction_fixture"):
        path = fake_bin / command
        path.write_text(fixture_script)
        path.chmod(0o700)

    mutation_stubs = "\n".join(
        f"{name}() {{ fixture_effect {name}; }}"
        for name in (
            "write_helper_install_receipt", "build_helper", "verify_installed_bundle",
            "sign_installed_bundle", "refresh_staged_bundle_state", "stop_existing_helper",
            "qa_kill_helper_install_if_requested", "clear_helper_install_receipt",
        )
    )
    # Keep the real staging-time trap order while replacing only filesystem staging effects.
    mutation_stubs += "\n" + shell_function(source, "install_bundle").split('  local icon_path=""', 1)[0]
    mutation_stubs += "  fixture_effect install_bundle\n}\n"
    preamble = functions + f'''
resolve_repo_python() {{ printf '%s\\n' {shlex.quote(sys.executable)}; }}
HELPER_CONFIG_FILE={shlex.quote(str(config))}
HELPER_RUNTIME_REPO_ROOT={shlex.quote(str(repo))}
APP_SUPPORT_DIR={shlex.quote(str(support))}
HELPER_APP_BUNDLE={shlex.quote(str(bundle))}
HELPER_EXECUTABLE_NAME=ViventiumHelper
LAUNCH_AGENT_PLIST={shlex.quote(str(support / 'persistent.plist'))}
HELPER_SELECTED_AGENT_PLIST={shlex.quote(str(support / 'persistent.plist'))}
STAGED_APP_BUNDLE={shlex.quote(str(tmp_path / 'staged.app'))}
HELPER_STAGE_STATE=fixture-stage
HELPER_DESTINATION_STATE=fixture-destination
HELPER_TRANSACTION_PYTHON={shlex.quote(str(fake_bin / 'transaction_fixture'))}
HELPER_TRANSACTION_TOOL=fixture-transaction-tool
RECOVERY_HELPER_SUPERVISOR_UNLOADED=0
RECOVERY_HELPER_SUPERVISOR_PLIST=
SKIP_LAUNCHCTL=0
LAUNCH_AFTER_INSTALL=1
verify_preserved_helper_config() {{ :; }}
'''

    def run(*, loaded: bool, helpers: int, foreign: bool = False,
            full_branch: bool = False, was_running: bool = True,
            session_job: bool = False, fail_activation: bool = False,
            fail_rollback: bool = False, untrusted_job_path: bool = False,
            normal_producer: bool = False, launch_after: bool = True, skip_launchctl: bool = False,
            bootout_unloaded_failure: bool = False, bootout_delayed_failure: bool = False,
            bootout_refused: bool = False):
        generation = "new" if normal_producer else "old"
        state_path.write_text(json.dumps({"loaded": loaded, "helpers": helpers,
            "program": str(tmp_path / "Other.app/Contents/MacOS/Other") if foreign else str(executable),
            "job_path": str(tmp_path / "untrusted.plist") if untrusted_job_path else
                str(session_plist if session_job else persistent_plist),
            "calls": [], "kickstarts": [], "bootstrap_paths": [], "opens": 0, "effects": [],
            "bundle_generation": generation, "mapped_generations": [generation] * helpers,
            "fail_activation": fail_activation, "fail_rollback": fail_rollback,
            "bootout_unloaded_failure": bootout_unloaded_failure,
            "bootout_delayed_failure": bootout_delayed_failure, "bootout_refused": bootout_refused,
            "pending_unload_checks": 0, "supervisor_restore_flag": 0, "timeline": []}))
        state = json.loads(state_path.read_text())
        state["allow_forced_kickstart"] = normal_producer
        state_path.write_text(json.dumps(state))
        script = "set -Eeuo pipefail\n" + preamble + mutation_stubs + "\n"
        script += 'trap \'fixture_exit_state "${RECOVERY_HELPER_SUPERVISOR_UNLOADED:-0}"\' EXIT\n'
        if normal_producer:
            script += (f"LAUNCH_AFTER_INSTALL={int(launch_after)}\nSKIP_LAUNCHCTL={int(skip_launchctl)}\n"
                       "bootstrap_launch_agent\nlaunch_helper_app\n")
        else:
            script += branch if full_branch else f"local_helper_was_running={int(was_running)}\n" + tail
        # Execute only fixture copies; an absolute native open cannot escape the test.
        script = script.replace("/usr/bin/open", "open_fixture")
        result = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=10,
            env={**os.environ, "PATH": str(fake_bin) + os.pathsep + os.environ["PATH"],
                 "FIXTURE_STATE": str(state_path), "FIXTURE_BUNDLE": str(bundle)})
        assert config.read_bytes() == original_config
        return result, json.loads(state_path.read_text())

    return run


def test_bundle_recovery_reuses_a_loaded_owner_without_opening_a_second_helper(recovery_run) -> None:
    result, state = recovery_run(loaded=True, helpers=1)
    assert result.returncode == 0, result.stderr
    assert state["helpers"] == 1, "Recovery must not open a second GUI helper beside the loaded native owner"
    assert state["opens"] == 0
    assert len(state["kickstarts"]) == 1
    assert "-k" not in state["kickstarts"][0]


def test_bundle_recovery_preserves_an_existing_manual_helper_when_unloaded(recovery_run) -> None:
    result, state = recovery_run(loaded=False, helpers=1)
    assert result.returncode == 0, result.stderr
    assert state["helpers"] == 1 and state["opens"] == 0
    assert state["kickstarts"] == []


def test_bundle_recovery_opens_once_when_neither_owner_nor_manual_helper_is_running(recovery_run) -> None:
    result, state = recovery_run(loaded=False, helpers=0)
    assert result.returncode == 0, result.stderr
    assert state["helpers"] == state["opens"] == 1
    assert state["kickstarts"] == []


def test_bundle_recovery_does_not_reopen_an_initially_stopped_helper(recovery_run) -> None:
    result, state = recovery_run(loaded=False, helpers=0, was_running=False)
    assert result.returncode == 0, result.stderr
    assert state["helpers"] == state["opens"] == 0
    assert state["kickstarts"] == []


def test_foreign_loaded_binding_is_refused_before_bundle_or_process_mutation(recovery_run) -> None:
    result, state = recovery_run(loaded=True, helpers=1, foreign=True, full_branch=True)
    assert result.returncode != 0
    assert "Refusing unrelated loaded helper supervisor" in result.stderr
    assert state["effects"] == []
    assert state["helpers"] == 1 and state["opens"] == 0
    assert state["kickstarts"] == []


@pytest.mark.parametrize("session_job", [False, True], ids=["persistent", "current-session"])
def test_bundle_recovery_pauses_old_owner_before_activation_and_restores_new_owner(recovery_run, session_job: bool) -> None:
    result, state = recovery_run(loaded=True, helpers=1, full_branch=True, session_job=session_job)
    assert result.returncode == 0, result.stderr
    assert state["helpers"] == 1
    assert state["mapped_generations"] == ["new"], "KeepAlive must not retain an old mapped helper after activation"
    assert state["opens"] == 0
    assert state["bootstrap_paths"] == [state["job_path"]]
    timeline = state["timeline"]
    paused = next(i for i, event in enumerate(timeline) if event["tool"] == "launchctl" and event["args"][0] == "bootout")
    stopped = next(i for i, event in enumerate(timeline) if event["tool"] == "fixture_effect" and event["args"][0] == "stop_existing_helper")
    activated = next(i for i, event in enumerate(timeline) if event["tool"] == "transaction_fixture" and event["args"][1] == "activate")
    resumed = next(i for i, event in enumerate(timeline) if event["tool"] == "launchctl" and event["args"][0] == "bootstrap")
    assert paused < stopped < activated < resumed
    assert timeline[stopped]["mapped"] == timeline[activated]["mapped"] == []
    assert timeline[resumed]["mapped"] == ["new"]
    assert len(state["kickstarts"]) == 1 and "-k" not in state["kickstarts"][0]


def test_failed_activation_restores_old_bundle_before_the_same_native_job(recovery_run) -> None:
    result, state = recovery_run(loaded=True, helpers=1, full_branch=True,
                                 session_job=True, fail_activation=True)
    assert result.returncode == 42
    assert "restored the previously owned helper bundle" in result.stderr
    assert state["bundle_generation"] == "old"
    assert state["loaded"] and state["helpers"] == 1
    assert state["mapped_generations"] == ["old"]
    assert state["bootstrap_paths"] == [state["job_path"]] and state["opens"] == 0
    timeline = state["timeline"]
    rolled_back = next(i for i, event in enumerate(timeline) if event["tool"] == "transaction_fixture" and event["args"][1] == "rollback-persisted")
    resumed = next(i for i, event in enumerate(timeline) if event["tool"] == "launchctl" and event["args"][0] == "bootstrap")
    assert rolled_back < resumed
    assert timeline[rolled_back]["mapped"] == []
    assert timeline[resumed]["mapped"] == ["old"]


def test_failed_rollback_does_not_restart_a_supervisor_on_an_unrestored_bundle(recovery_run) -> None:
    result, state = recovery_run(loaded=True, helpers=1, full_branch=True,
                                 fail_activation=True, fail_rollback=True)
    assert result.returncode == 42
    assert "retained the owned backup for recovery" in result.stderr
    assert not state["loaded"] and state["helpers"] == 0
    assert state["mapped_generations"] == []
    assert state["bootstrap_paths"] == state["kickstarts"] == []
    assert state["opens"] == 0


def test_untrusted_loaded_plist_is_refused_before_retiring_the_old_helper(recovery_run) -> None:
    result, state = recovery_run(loaded=True, helpers=1, full_branch=True, untrusted_job_path=True)
    assert result.returncode != 0
    assert "Refusing an unrecognized helper supervisor path" in result.stderr
    assert state["loaded"] and state["helpers"] == 1 and state["mapped_generations"] == ["old"]
    assert "stop_existing_helper" not in state["effects"]
    assert "transaction:activate" not in state["effects"]
    assert state["bootstrap_paths"] == state["kickstarts"] == []
    assert state["opens"] == 0


def test_full_bundle_refresh_preserves_an_initially_stopped_unloaded_helper(recovery_run) -> None:
    result, state = recovery_run(loaded=False, helpers=0, full_branch=True)
    assert result.returncode == 0, result.stderr
    assert not state["loaded"] and state["helpers"] == state["opens"] == 0
    assert state["mapped_generations"] == []
    assert state["bootstrap_paths"] == state["kickstarts"] == []


def test_uncertain_bootout_failure_restores_old_native_owner_and_keeps_original_failure(recovery_run) -> None:
    result, state = recovery_run(loaded=True, helpers=1, full_branch=True, session_job=True,
                                 bootout_unloaded_failure=True)
    assert "transaction:rollback-persisted" in state["effects"], result.stderr
    assert state["loaded"], "A bootout error after actual unload must not leave the prior native owner missing"
    assert state["helpers"] == 1 and state["mapped_generations"] == ["old"]
    assert state["bundle_generation"] == "old"
    assert result.returncode == 36, "Preserve the original native pause failure"
    assert state["bootstrap_paths"] == [state["job_path"]] and state["opens"] == 0
    assert len(state["kickstarts"]) == 1 and "-k" not in state["kickstarts"][0]
    assert "transaction:activate" not in state["effects"]
    timeline = state["timeline"]
    rolled_back = next(i for i, event in enumerate(timeline) if event["tool"] == "transaction_fixture" and event["args"][1] == "rollback-persisted")
    resumed = next(i for i, event in enumerate(timeline) if event["tool"] == "launchctl" and event["args"][0] == "bootstrap")
    assert rolled_back < resumed


def test_delayed_bootout_failure_waits_for_absence_before_restoring_old_owner(recovery_run) -> None:
    result, state = recovery_run(loaded=True, helpers=1, full_branch=True, session_job=True,
                                 bootout_delayed_failure=True)
    assert result.returncode == 36
    assert state["loaded"], "A still-visible pending bootout must settle before supervisor restoration is claimed"
    assert state["helpers"] == 1 and state["mapped_generations"] == ["old"]
    assert state["bundle_generation"] == "old" and state["supervisor_restore_flag"] == 0
    assert state["bootstrap_paths"] == [state["job_path"]]
    assert len(state["kickstarts"]) == 1 and "-k" not in state["kickstarts"][0]
    assert state["opens"] == 0


def test_true_bootout_refusal_stays_bounded_without_claiming_a_restored_supervisor(recovery_run) -> None:
    started = time.monotonic()
    result, state = recovery_run(loaded=True, helpers=1, full_branch=True, bootout_refused=True)
    assert time.monotonic() - started < 3.5
    assert result.returncode == 36
    assert state["loaded"] and state["helpers"] == 1 and state["mapped_generations"] == ["old"]
    assert state["supervisor_restore_flag"] == 1
    assert state["bootstrap_paths"] == state["kickstarts"] == []
    assert state["opens"] == 0


def test_normal_install_reuses_the_helper_started_by_its_native_owner(recovery_run) -> None:
    result, state = recovery_run(loaded=False, helpers=0, normal_producer=True)
    assert result.returncode == 0, result.stderr
    assert state["helpers"] == 1, "Normal install must not open another GUI helper after native bootstrap"
    assert state["mapped_generations"] == ["new"]
    assert state["opens"] == 0
    assert state["bootstrap_paths"] == [state["job_path"]]
    assert any("-k" in call for call in state["kickstarts"]), "Retain the normal install's existing native bootstrap"


def test_normal_install_with_launch_disabled_does_not_start_or_open_a_helper(recovery_run) -> None:
    result, state = recovery_run(loaded=False, helpers=0, normal_producer=True, launch_after=False)
    assert result.returncode == 0, result.stderr
    assert state["helpers"] == state["opens"] == 0
    assert state["bootstrap_paths"] == state["kickstarts"] == []


@pytest.mark.parametrize("manual_helpers,expected_opens", [(0, 1), (1, 0)])
def test_normal_install_without_launchctl_opens_only_a_missing_manual_helper(
    recovery_run, manual_helpers: int, expected_opens: int,
) -> None:
    result, state = recovery_run(loaded=False, helpers=manual_helpers, normal_producer=True, skip_launchctl=True)
    assert result.returncode == 0, result.stderr
    assert state["helpers"] == 1 and state["mapped_generations"] == ["new"]
    assert state["opens"] == expected_opens
    assert state["bootstrap_paths"] == state["kickstarts"] == []

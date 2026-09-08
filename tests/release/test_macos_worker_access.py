from __future__ import annotations

import json
import os
import plistlib
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "apps/macos/ViventiumHelper"
SOURCE = HELPER / "Sources/ViventiumHelper/ViventiumHelperApp.swift"


def test_helper_dispatches_native_and_source_cli_with_their_own_argument_contract(tmp_path: Path):
    source = SOURCE.read_text()
    policy = "enum HelperCLICommand {" + source.split("enum HelperCLICommand {", 1)[1].split(
        "enum RuntimeDesiredState:", 1
    )[0]
    harness = tmp_path / "arguments.swift"
    harness.write_text(
        "import Foundation\n" + policy + "\n"
        "let values = HelperCLICommand.arguments(repoRoot: CommandLine.arguments[1], "
        "appSupportDir: CommandLine.arguments[2], command: [CommandLine.arguments.count > 3 ? CommandLine.arguments[3] : \"start\"])\n"
        "let data = try JSONSerialization.data(withJSONObject: values)\n"
        "print(String(decoding: data, as: UTF8.self))\n"
    )
    compiled = tmp_path / "helper-arguments"
    subprocess.run(["xcrun", "swiftc", str(harness), "-o", str(compiled)], check=True, capture_output=True)
    support = tmp_path / "support with spaces"
    source_root = tmp_path / "source"
    args = json.loads(subprocess.check_output([str(compiled), str(source_root), str(support)]))
    assert args == [str(source_root / "bin/viventium"), "--app-support-dir", str(support), "start"]

    native_root = tmp_path / "native"
    (native_root / "bin").mkdir(parents=True)
    cli = native_root / "bin/viventium"
    cli.write_bytes((ROOT / "scripts/viventium/native_cli.sh").read_bytes())
    start = native_root / "bin/viventium-native-start"
    start.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$VIVENTIUM_TEST_ARGUMENTS"\n')
    start.chmod(0o700)
    args = json.loads(subprocess.check_output([str(compiled), str(native_root), str(support)]))
    assert args == [str(cli), "start"]
    launch_args = json.loads(subprocess.check_output([str(compiled), str(native_root), str(support), "launch"]))
    assert launch_args == [str(cli), "start", "--respect-stopped"]
    receipt = tmp_path / "arguments.txt"
    environment = dict(os.environ, VIVENTIUM_APP_SUPPORT_DIR=str(support), VIVENTIUM_TEST_ARGUMENTS=str(receipt))
    # Exercise the real native CLI parser. The old helper command exited at usage
    # before it could reach this declared native-start entrypoint.
    subprocess.run(["/bin/bash", *args], env=environment, check=True, capture_output=True)
    assert receipt.read_text().splitlines() == ["--app-support-dir", str(support)]
    subprocess.run(["/bin/bash", *launch_args], env=environment, check=True, capture_output=True)
    assert receipt.read_text().splitlines() == ["--app-support-dir", str(support), "--respect-stopped"]


def test_permission_setup_checks_live_os_grants_without_changing_tcc_or_stopping_work():
    source = SOURCE.read_text()
    controller = source.split("private final class ComputerAccessController:", 1)[1].split(
        "enum HelperCLICommand", 1
    )[0]
    assert "AXIsProcessTrusted()" in controller
    assert "CGPreflightScreenCaptureAccess()" in controller
    assert "AXIsProcessTrustedWithOptions(options as CFDictionary)" in controller
    assert "CGRequestScreenCaptureAccess()" in controller
    assert "Privacy_AllFiles" in controller
    assert "Computer Access…" in source
    assert "computerAccessSetupShown" in source
    for forbidden in ("tccutil", "TCC.db", "sudo", "kill(", "stopStack", "startStack"):
        assert forbidden not in controller


def test_hardened_helper_has_automation_purpose_and_signing_entitlement():
    with (HELPER / "Sources/ViventiumHelper/Resources/Info.plist").open("rb") as handle:
        info = plistlib.load(handle)
    assert info["CFBundleIdentifier"] == "ai.viventium.helper"
    assert info["NSAppleEventsUsageDescription"]
    with (HELPER / "ViventiumHelper.entitlements").open("rb") as handle:
        assert plistlib.load(handle) == {"com.apple.security.automation.apple-events": True}
    installer = (ROOT / "scripts/viventium/install_macos_helper.sh").read_text()
    assert '"AssociatedBundleIdentifiers": ["ai.viventium.helper"]' in installer
    assert '--entitlements "$HELPER_PACKAGE_DIR/ViventiumHelper.entitlements"' in installer
    for name in ("native-payload-candidate.yml", "native-payload-release.yml"):
        workflow = (ROOT / ".github/workflows" / name).read_text()
        assert "--entitlements apps/macos/ViventiumHelper/ViventiumHelper.entitlements" in workflow


def _native_runtime():
    import importlib.util
    spec = importlib.util.spec_from_file_location("native_worker_access_test", ROOT / "scripts/viventium/native_runtime.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _owned_app(path: Path):
    (path / "Contents/MacOS").mkdir(parents=True)
    marker = path / "Contents/Resources/viventium-owner.json"
    marker.parent.mkdir()
    marker.write_text(json.dumps({"product": "ai.viventium.helper", "schema_version": 1}))
    (path / "Contents/MacOS/ViventiumHelper").write_text("synthetic helper\n")


def _install_fixture(tmp_path, monkeypatch, *, no_start=False, no_helper=False):
    import argparse
    from contextlib import contextmanager
    runtime = _native_runtime()
    root = tmp_path / "release"
    support = tmp_path / "support"
    home = tmp_path / "home"
    home.mkdir()
    defaults = root / "runtime/defaults"
    defaults.mkdir(parents=True)
    (defaults / "config.yaml").write_text("synthetic: true\n")
    (defaults / "native-runtime.env").write_text("")
    _owned_app(root / "apps/Viventium.app")
    events = []
    locks = []

    @contextmanager
    def lock(*_args, **_kwargs):
        assert not locks, "nested lifecycle lock would deadlock helper start"
        locks.append(True)
        try:
            yield
        finally:
            locks.pop()

    monkeypatch.setattr(runtime, "lifecycle_lock", lock)
    monkeypatch.setattr(runtime, "release_root", lambda: root)
    monkeypatch.setattr(runtime, "default_support", lambda: support)
    monkeypatch.setattr(runtime, "user_home", lambda: home)
    for name in ("packaged_health", "refuse_cross_mode_install", "preflight_service_ports", "prepare_data_schema", "runtime_secrets", "load_native_runtime_env"):
        monkeypatch.setattr(runtime, name, lambda *_args, **_kwargs: None)
    monkeypatch.setattr(runtime, "guard_pid_snapshot", lambda *_args: {})
    monkeypatch.setattr(runtime, "helper_processes", lambda _app: {})
    monkeypatch.setattr(runtime, "quiesce_helper", lambda _app: events.append("quiesce"))
    monkeypatch.setattr(runtime, "stop_attempt_services", lambda *_args: events.append("stop-attempt"))

    def open_app(command, **_kwargs):
        assert command[:2] == ["/usr/bin/open", "-gj"]
        assert not locks, "installed app must launch after install lock releases"
        events.append("open-helper")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(runtime.subprocess, "run", open_app)
    monkeypatch.setattr(runtime, "health", lambda _args: events.append("health"))

    def direct_start(_args, *, _lock_held):
        assert locks and _lock_held
        events.append("direct-start")

    monkeypatch.setattr(runtime, "start", direct_start)
    args = argparse.Namespace(app_support_dir=support, local_qa=False, no_helper=no_helper,
                              no_start=no_start, no_open=True, timeout=0)
    return runtime, args, root, support, home, events, locks


def test_native_first_start_uses_installed_helper_after_lock_release(tmp_path, monkeypatch):
    runtime, args, root, support, home, events, _ = _install_fixture(tmp_path, monkeypatch)
    runtime.install(args)
    assert events == ["open-helper", "health"]
    config = json.loads((support / "helper-config.json").read_text())
    assert config["repoRoot"] == str(root)
    assert config["runtimeSupervision"]["desiredState"] == "running"
    assert (home / "Applications/Viventium.app").is_dir()


def test_native_no_start_preserves_setup_and_keeps_helper_stopped(tmp_path, monkeypatch):
    runtime, args, _, support, _, events, _ = _install_fixture(tmp_path, monkeypatch, no_start=True)
    runtime.write_atomic(support / "helper-config.json", json.dumps({
        "computerAccessSetupShown": True, "showInStatusBar": False, "futurePreference": {"keep": 7},
        "runtimeSupervision": {"futurePolicy": "keep"},
    }))
    runtime.install(args)
    config = json.loads((support / "helper-config.json").read_text())
    assert config["computerAccessSetupShown"] is True
    assert config["showInStatusBar"] is False
    assert config["futurePreference"] == {"keep": 7}
    assert config["runtimeSupervision"]["futurePolicy"] == "keep"
    assert config["runtimeSupervision"]["desiredState"] == "stopped"
    assert events == ["open-helper"]


def test_failed_helper_health_quiesces_before_rollback_and_restores_exact_config(tmp_path, monkeypatch):
    import pytest
    runtime, args, _, support, home, events, _ = _install_fixture(tmp_path, monkeypatch)
    previous_config = '{ "computerAccessSetupShown": true, "future": [1, 2] }\n'
    runtime.write_atomic(support / "helper-config.json", previous_config)
    previous_state = '{"schema_version":1,"release_root":"/synthetic/prior"}\n'
    runtime.write_atomic(support / "state/native-runtime.json", previous_state)
    target = home / "Applications/Viventium.app"
    _owned_app(target)
    (target / "prior.txt").write_text("keep")

    def unavailable(_args):
        raise runtime.RuntimeError_("synthetic unavailable worker")

    monkeypatch.setattr(runtime, "health", unavailable)
    with pytest.raises(runtime.RuntimeError_, match="synthetic unavailable worker"):
        runtime.install(args)
    assert events.index("open-helper") < events.index("stop-attempt")
    assert events[events.index("stop-attempt") - 1] == "quiesce"
    assert (target / "prior.txt").read_text() == "keep"
    assert (support / "helper-config.json").read_text() == previous_config
    assert (support / "state/native-runtime.json").read_text() == previous_state


def test_native_explicit_no_helper_keeps_direct_guarded_start(tmp_path, monkeypatch):
    runtime, args, _, support, home, events, _ = _install_fixture(tmp_path, monkeypatch, no_helper=True)
    runtime.install(args)
    assert events == ["direct-start", "health"]
    assert not (support / "helper-config.json").exists()
    assert not (home / "Applications/Viventium.app").exists()


def test_native_rollbacks_cannot_replace_a_newer_installation(tmp_path, monkeypatch):
    import pytest
    runtime, args, _, support, home, events, _ = _install_fixture(tmp_path, monkeypatch)

    def changed(_args):
        state = json.loads((support / "state/native-runtime.json").read_text())
        state["installation_id"] = "synthetic-newer-installation"
        runtime.write_atomic(support / "state/native-runtime.json", json.dumps(state))
        raise runtime.RuntimeError_("synthetic startup failure")

    monkeypatch.setattr(runtime, "health", changed)
    with pytest.raises(runtime.RuntimeError_, match="newer installation was preserved"):
        runtime.install(args)
    assert "quiesce" not in events
    assert "stop-attempt" not in events
    assert (home / "Applications/Viventium.app").is_dir()
    assert json.loads((support / "state/native-runtime.json").read_text())["installation_id"] == "synthetic-newer-installation"


def test_helper_quiescence_stops_only_the_actual_owned_app_child(tmp_path):
    import time
    runtime = _native_runtime()
    app = tmp_path / "Viventium.app"
    _owned_app(app)
    executable = app / "Contents/MacOS/ViventiumHelper"
    harness = tmp_path / "helper.c"
    harness.write_text("#include <unistd.h>\nint main(void) {sleep(60); return 0;}\n")
    subprocess.run(["xcrun", "clang", str(harness), "-o", str(executable)], check=True, capture_output=True)
    owned = subprocess.Popen([str(executable)])
    unrelated = subprocess.Popen(["/bin/sleep", "60"])
    try:
        deadline = time.monotonic() + 3
        while owned.pid not in runtime.helper_processes(app) and time.monotonic() < deadline:
            time.sleep(0.02)
        assert set(runtime.helper_processes(app)) == {owned.pid}
        runtime.quiesce_helper(app, timeout=1)
        assert owned.wait(timeout=2) != 0
        assert unrelated.poll() is None
    finally:
        for child in (owned, unrelated):
            if child.poll() is None:
                child.terminate()
            child.wait(timeout=2)


def test_native_first_start_cannot_certify_preexisting_worker_children(tmp_path, monkeypatch):
    import pytest
    runtime, args, _, support, _, events, _ = _install_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(runtime, "guard_pid_snapshot", lambda *_args: {"glasshive": 123})
    with pytest.raises(runtime.RuntimeError_, match="supported Bootstrap update"):
        runtime.install(args)
    assert not support.exists()
    assert events == []


def test_native_successful_health_cannot_complete_a_superseded_install(tmp_path, monkeypatch, capsys):
    import pytest
    runtime, args, _, support, _, events, _ = _install_fixture(tmp_path, monkeypatch)

    def newer_but_healthy(_args):
        state = json.loads((support / "state/native-runtime.json").read_text())
        state["installation_id"] = "synthetic-newer-installation"
        runtime.write_atomic(support / "state/native-runtime.json", json.dumps(state))

    monkeypatch.setattr(runtime, "health", newer_but_healthy)
    with pytest.raises(runtime.RuntimeError_, match="newer installation was preserved"):
        runtime.install(args)
    assert "Viventium Native installed" not in capsys.readouterr().out
    assert events == ["open-helper"]


def _installed_lifecycle_fixture(tmp_path, monkeypatch):
    import argparse
    from contextlib import contextmanager
    runtime = _native_runtime()
    root, support, home = tmp_path / "release", tmp_path / "support", tmp_path / "home"
    root.mkdir()
    events, locks = [], []

    @contextmanager
    def lock(*_args, **_kwargs):
        assert not locks
        locks.append(True)
        try:
            yield
        finally:
            locks.pop()

    monkeypatch.setattr(runtime, "lifecycle_lock", lock)
    monkeypatch.setattr(runtime, "release_root", lambda: root)
    monkeypatch.setattr(runtime, "default_support", lambda: support)
    monkeypatch.setattr(runtime, "user_home", lambda: home)
    runtime.write_atomic(support / "state/native-runtime.json", json.dumps({
        "schema_version": 1, "release_root": str(root),
    }))
    runtime.write_atomic(support / "helper-config.json", json.dumps({
        "nativeRuntime": True, "repoRoot": str(root), "appSupportDir": str(support),
        "computerAccessSetupShown": True, "futurePreference": 7,
        "runtimeSupervision": {"desiredState": "running", "futurePolicy": "keep"},
    }))

    def quiesce(app):
        assert locks and app == home / "Applications/Viventium.app"
        # A live supervisor may save its cached running intent up to termination.
        config = json.loads((support / "helper-config.json").read_text())
        config["runtimeSupervision"]["desiredState"] = "running"
        runtime.write_atomic(support / "helper-config.json", json.dumps(config))
        events.append("quiesce")

    def stop_services(services, actual_support, actual_root):
        assert locks and (actual_support, actual_root) == (support, root)
        assert json.loads((support / "helper-config.json").read_text())["runtimeSupervision"]["desiredState"] == "stopped"
        assert list(services) == list(reversed(runtime.SERVICE_ORDER))
        events.append("stop-services")

    monkeypatch.setattr(runtime, "quiesce_helper", quiesce)
    monkeypatch.setattr(runtime, "stop_services", stop_services)
    monkeypatch.delenv("VIVENTIUM_HELPER_STOP_BACKGROUND_NATIVE", raising=False)
    return runtime, argparse.Namespace(app_support_dir=support), root, support, events, locks


def test_external_stop_retires_supervisor_before_storing_stop_and_blocks_queued_start(tmp_path, monkeypatch, capsys):
    runtime, args, _, support, events, _ = _installed_lifecycle_fixture(tmp_path, monkeypatch)
    runtime.stop(args)
    assert events == ["quiesce", "stop-services"]
    config = json.loads((support / "helper-config.json").read_text())
    assert config["computerAccessSetupShown"] and config["futurePreference"] == 7
    assert config["runtimeSupervision"]["futurePolicy"] == "keep"
    monkeypatch.setattr(runtime, "packaged_health", lambda *_args: (_ for _ in ()).throw(AssertionError("queued start must not start services")))
    args.respect_stopped = True
    runtime.start(args)
    assert "Viventium remains stopped" in capsys.readouterr().out
    assert events == ["quiesce", "stop-services"]


def test_helper_menu_stop_preserves_live_start_control(tmp_path, monkeypatch):
    runtime, args, _, support, events, _ = _installed_lifecycle_fixture(tmp_path, monkeypatch)
    monkeypatch.setenv("VIVENTIUM_HELPER_STOP_BACKGROUND_NATIVE", "1")
    runtime.stop(args)
    assert events == ["stop-services"]
    assert json.loads((support / "helper-config.json").read_text())["runtimeSupervision"]["desiredState"] == "stopped"


def test_explicit_native_start_can_restart_after_intentional_stop(tmp_path, monkeypatch):
    import pytest
    runtime, args, _, support, _, locks = _installed_lifecycle_fixture(tmp_path, monkeypatch)
    runtime.stop(args)

    def reached_owned_start(_root):
        assert locks
        assert json.loads((support / "helper-config.json").read_text())["runtimeSupervision"]["desiredState"] == "running"
        raise runtime.RuntimeError_("synthetic packaged-health boundary reached")

    monkeypatch.setattr(runtime, "packaged_health", reached_owned_start)
    with pytest.raises(runtime.RuntimeError_, match="synthetic packaged-health boundary reached"):
        runtime.start(args)


def test_native_lifecycle_preserves_a_foreign_helper_binding(tmp_path, monkeypatch):
    import pytest
    runtime, args, _, support, events, _ = _installed_lifecycle_fixture(tmp_path, monkeypatch)
    config_path = support / "helper-config.json"
    config = json.loads(config_path.read_text())
    config["repoRoot"] = "/synthetic/another-runtime"
    runtime.write_atomic(config_path, json.dumps(config))
    before = config_path.read_bytes()
    for operation in (runtime.stop, runtime.start):
        with pytest.raises(runtime.RuntimeError_, match="belongs to another runtime"):
            operation(args)
        assert config_path.read_bytes() == before
    assert events == []

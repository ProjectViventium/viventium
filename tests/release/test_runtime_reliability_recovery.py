"""Deterministic runtime fault/recovery contracts; all resources are synthetic."""
from __future__ import annotations

import importlib.util
import json
import os
import plistlib
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "bin/viventium"
INSTALLER = ROOT / "scripts/viventium/install_macos_helper.sh"
HELPER = ROOT / "apps/macos/ViventiumHelper/Sources/ViventiumHelper/ViventiumHelperApp.swift"
START = ROOT / "viventium_v0_4/viventium-librechat-start.sh"


def shell_function(path: Path, name: str) -> str:
    lines = path.read_text().splitlines()
    start = next(index for index, line in enumerate(lines) if line.strip() == name + "() {")
    collected: list[str] = []
    depth = 0
    for line in lines[start:]:
        collected.append(line)
        depth += line.count("{") - line.count("}")
        if depth == 0:
            break
    return "\n".join(collected) + "\n"


def shell(script: str, **environment: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["bash", "-c", "set -euo pipefail\n" + script],
                          capture_output=True, text=True, env={**os.environ, **environment})


@pytest.mark.parametrize("missing,watchdog,topology,expected", [
    ("api", False, "", 0), ("api", True, "", 1),
    ("frontend", True, "", 0), ("voice", True, "", 0),
    ("xperfect", False, "", 0), ("xperfect", False, "external_split", 1),
    ("xperfect", True, "", 1), ("", True, "", 1),
])
def test_recovery_requires_local_process_loss_without_a_live_recovery_owner(
    missing: str, watchdog: bool, topology: str, expected: int,
) -> None:
    script = shell_function(CLI, "runtime_owned_recovery_needed") + r'''
assign_runtime_ports() { api_port=10001 frontend_port=10002 playground_port=10003; }
runtime_port_listening() {
  [[ ! ( "$MISSING" == api && "$1" == 10001 ) && ! ( "$MISSING" == frontend && "$1" == 10002 ) ]]
}
express_install_experience() { return 0; }
telegram_recovery_owner_missing() { return 1; }
runtime_env_true() {
  [[ ( "$1" == START_GLASSHIVE && "$MISSING" == xperfect ) || ( "$1" == VIVENTIUM_VOICE_ENABLED && "$MISSING" == voice ) ]]
}
read_generated_env_value() { printf '%s\n' "$TOPOLOGY"; }
runtime_pid_file_running() {
  [[ "$2" == true ]] || exit 90
  [[ "$1" == *watchdog* && "$WATCHDOG" == true ]]
}
runtime_owned_recovery_needed
'''
    result = shell(script, MISSING=missing, WATCHDOG=str(watchdog).lower(), TOPOLOGY=topology)
    assert result.returncode == expected, result.stderr


@pytest.mark.parametrize("claim,recovery,stop", [(False, True, True), (False, False, False), (True, True, False)])
def test_serving_group_is_not_a_startup_claim(tmp_path: Path, claim: bool, recovery: bool, stop: bool) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("version: 1\n")
    script = shell_function(CLI, "launch_stack_detached") + r'''
ensure_app_support_layout() { :; }
initialize_telegram_user_config_authority() { :; }
user_surface_healthy() { return 1; }
runtime_start_claim_active() { [[ "$CLAIM" == true ]]; }
detached_launch_process_group_running() { return 0; }
runtime_owned_recovery_needed() { [[ "$RECOVERY" == true ]]; }
stop_stack_for_upgrade() {
  [[ "$VIVENTIUM_PRESERVE_HELPER_RUNTIME_INTENT" == 1 ]] || exit 91
  echo owned-stop; return 42;
}
is_stack_running() { echo unexpected-fallthrough; exit 92; }
launch_stack_detached
'''
    result = shell(script, CONFIG_FILE=str(config), APP_SUPPORT_DIR=str(tmp_path),
                   CLAIM=str(claim).lower(), RECOVERY=str(recovery).lower())
    assert result.returncode == (1 if stop else 0), result.stderr
    assert ("owned-stop" in result.stdout) == stop
    assert "unexpected" not in result.stdout
    if claim:
        assert "already starting" in result.stdout
    elif not recovery:
        assert "available services are preserved" in result.stdout


def test_launchd_policy_restarts_crashes_but_not_clean_quit(tmp_path: Path) -> None:
    target = tmp_path / "helper.plist"
    script = shell_function(INSTALLER, "write_launch_agent_plist") + r'''
resolve_repo_python() { printf '%s\n' "$PYTHON"; }
default_public_install_repo_root() { printf /public/viventium; }
HELPER_SELECTED_AGENT_PLIST="$TARGET"
HELPER_APP_BUNDLE=/Applications/Viventium.app
HELPER_EXECUTABLE_NAME=ViventiumHelper
HELPER_RUNTIME_REPO_ROOT=/public/viventium
HELPER_LOG_FILE=/private/runtime/helper.log
write_launch_agent_plist
'''
    result = shell(script, PYTHON=sys.executable, TARGET=str(target))
    assert result.returncode == 0, result.stderr
    job = plistlib.loads(target.read_bytes())
    assert job["KeepAlive"] == {"SuccessfulExit": False}
    assert job["ThrottleInterval"] == 10
    assert job["RunAtLoad"] is True
    assert job["ProgramArguments"] == ["/Applications/Viventium.app/Contents/MacOS/ViventiumHelper"]
    assert target.stat().st_mode & 0o777 == 0o600


def test_existing_login_off_uses_session_registration(tmp_path: Path) -> None:
    config = tmp_path / "helper-config.json"
    config.write_text(json.dumps({"launchAtLogin": False}))
    result = shell(shell_function(INSTALLER, "select_helper_agent_path") + r'''
resolve_repo_python() { printf '%s\n' "$PYTHON"; }
HELPER_CONFIG_FILE="$CONFIG"
LAUNCH_AGENT_PLIST="$SUPPORT/persistent.plist"
APP_SUPPORT_DIR="$SUPPORT"
SKIP_LOGIN_ITEM=0
select_helper_agent_path
printf '%s\n%s\n' "$HELPER_LOGIN_PREFERENCE" "$HELPER_SELECTED_AGENT_PLIST"
''', PYTHON=sys.executable, CONFIG=str(config), SUPPORT=str(tmp_path))
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["false", str(tmp_path / "runtime/helper-supervisor.plist")]


def swift_run(tmp_path: Path, definitions: str, body: str) -> str:
    harness = tmp_path / "contract.swift"
    harness.write_text("import Foundation\nimport Darwin\n" + definitions +
                       "\n@main struct Contract { static func main() async throws {\n" + body + "\n} }\n")
    executable = tmp_path / "contract"
    build = subprocess.run(["xcrun", "swiftc", "-parse-as-library", str(harness), "-o", str(executable)],
                           capture_output=True, text=True)
    assert build.returncode == 0, build.stderr
    result = subprocess.run([str(executable), str(tmp_path / "config.json")], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_swift_stale_health_cannot_overwrite_stop_or_same_state_start(tmp_path: Path) -> None:
    source = HELPER.read_text()
    definitions = "enum RuntimeDesiredState:" + source.split("enum RuntimeDesiredState:", 1)[1].split("private struct ActiveRuntimeCheckout:", 1)[0]
    body = r'''
let url = URL(fileURLWithPath: CommandLine.arguments[1])
var original = HelperConfig(repoRoot: "/public/viventium", appSupportDir: "/private/viventium", runtimeSupervision: .defaultRunning)
try HelperConfigPreservingStore.save(config: original, to: url)
var stop = original
stop.runtimeSupervision!.requestStopped()
try HelperConfigPreservingStore.save(config: stop, to: url, supervisionWrite: .explicitIntent)
original.runtimeSupervision!.recordHealthy(at: Date(), stabilityWindow: 300)
do { try HelperConfigPreservingStore.save(config: original, to: url, supervisionWrite: .observed); preconditionFailure("stale health accepted") } catch { }
original.showInStatusBar = false
try HelperConfigPreservingStore.save(config: original, to: url)
var saved = try JSONDecoder().decode(HelperConfig.self, from: Data(contentsOf: url))
precondition(saved.runtimeSupervision!.desiredState == .stopped)
precondition(saved.showInStatusBar == false)
saved.runtimeSupervision!.requestRunning()
try HelperConfigPreservingStore.save(config: saved, to: url, supervisionWrite: .explicitIntent)
let previous = saved
saved.runtimeSupervision!.requestRunning()
try HelperConfigPreservingStore.save(config: saved, to: url, supervisionWrite: .explicitIntent)
precondition(saved.runtimeSupervision!.intentRevision != previous.runtimeSupervision!.intentRevision)
do { try HelperConfigPreservingStore.save(config: previous, to: url, supervisionWrite: .observed); preconditionFailure("older running intent accepted") } catch { }
let foreign = HelperConfig(repoRoot: "/public/other", appSupportDir: saved.appSupportDir, runtimeSupervision: saved.runtimeSupervision)
do { try HelperConfigPreservingStore.save(config: foreign, to: url, supervisionWrite: .explicitIntent); preconditionFailure("foreign binding accepted") } catch { }
print("intent-ok")
'''
    assert "intent-ok" in swift_run(tmp_path, definitions, body)


def test_helper_readiness_and_stop_use_different_contracts(tmp_path: Path) -> None:
    source = HELPER.read_text()
    definitions = "private struct RuntimePorts:" + source.split("private struct RuntimePorts:", 1)[1].split("private extension HelperController", 1)[0]
    methods = source.split("    nonisolated static func managedServicesRunning(runtime:", 1)[1].split("    nonisolated static func stackOwnedByDifferentRepo(", 1)[0]
    methods = "    nonisolated static func managedServicesRunning(runtime:" + methods
    definitions += "\nprivate class HelperController {\n" + methods + r'''
static var status = 503
static func firstHTTPStatus(urls: [URL]) async -> Int? { status }
static func candidateURLs(for url: URL) -> [URL] { [url] }
}
'''
    body = r'''
let support = URL(fileURLWithPath: CommandLine.arguments[1]).deletingLastPathComponent()
let runtimeDir = support.appendingPathComponent("runtime")
try FileManager.default.createDirectory(at: runtimeDir, withIntermediateDirectories: true)
try "START_GLASSHIVE=true\nGLASSHIVE_RUNTIME_PORT=28766\nGLASSHIVE_MCP_PORT=28767\nGLASSHIVE_UI_PORT=28780\nVIVENTIUM_VOICE_ENABLED=true\nVIVENTIUM_VOICE_GATEWAY_HEALTH_PORT=28301\nLIVEKIT_API_HOST=https://voice.example.invalid\n".write(to: runtimeDir.appendingPathComponent("runtime.env"), atomically: true, encoding: .utf8)
let runtime = RuntimeEnvParser().readRuntime(appSupportDir: support.path)
precondition(runtime.managedHealthCheckURLs!.contains("http://127.0.0.1:28766/health"))
precondition(runtime.managedHealthCheckURLs!.contains("http://127.0.0.1:28301/health"))
precondition(runtime.managedHealthCheckURLs!.contains("https://voice.example.invalid"))
precondition(!runtime.managedStopCheckURLs.contains("https://voice.example.invalid"))
precondition(await HelperController.managedServicesRunning(runtime: runtime))
precondition(!(await HelperController.managedServicesHealthy(runtime: runtime)))
HelperController.status = 200
precondition(await HelperController.managedServicesHealthy(runtime: runtime))
print("health-ok")
'''
    # Swift precondition uses a synchronous autoclosure.
    body = body.replace("precondition(await HelperController.managedServicesRunning(runtime: runtime))", "let live = await HelperController.managedServicesRunning(runtime: runtime); precondition(live)")
    body = body.replace("precondition(!(await HelperController.managedServicesHealthy(runtime: runtime)))", "let unready = await HelperController.managedServicesHealthy(runtime: runtime); precondition(!unready)")
    body = body.replace("precondition(await HelperController.managedServicesHealthy(runtime: runtime))", "let ready = await HelperController.managedServicesHealthy(runtime: runtime); precondition(ready)")
    assert "health-ok" in swift_run(tmp_path, definitions, body)


def test_redis_repair_precedes_backend_restart_and_explicitly_degrades(tmp_path: Path) -> None:
    script = shell_function(START, "restart_detached_librechat_backend") + r'''
SKIP_LIBRECHAT=false LIBRECHAT_DIR="$DIRECTORY"
PARALLEL_WORK_REQUESTED_AVAILABLE=true
PARALLEL_WORK_REQUESTED_USE_REDIS=true PARALLEL_WORK_REQUESTED_USE_REDIS_STREAMS=true PARALLEL_WORK_REQUESTED_REDIS_URI=redis://local
start_deferred_parallel_work_redis() { echo dependency; return "$REDIS_RESULT"; }
log_warn() { :; }
is_truthy() { [[ "$1" == true ]]; }
load_local_qa_runtime_control() { :; }
kill_port_listeners() {
  if [[ "$REDIS_RESULT" == 0 ]]; then [[ "$USE_REDIS" == true ]]; else [[ "$USE_REDIS" == false && "$VIVENTIUM_PARALLEL_WORK_AVAILABLE" == false ]]; fi
  echo restart; exit 41;
}
LC_API_PORT=10001 VIVENTIUM_SANDPACK_BUNDLER_PORT=10002
restart_detached_librechat_backend
'''
    for status in ["0", "1"]:
        result = shell(script, DIRECTORY=str(tmp_path), REDIS_RESULT=status)
        assert result.returncode == 41, result.stderr
        assert result.stdout.splitlines() == ["dependency", "restart"]
    healthy = shell_function(START, "librechat_api_healthy")
    assert "sandpack" not in healthy


def test_log_rotation_preserves_failures_and_refuses_linked_history(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location("native_runtime", ROOT / "scripts/viventium/native_runtime.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    log = tmp_path / "service.log"
    log.write_text("original failure\n")
    module.rotate_log(log, maximum_bytes=1)
    previous = tmp_path / "service.log.1"
    assert previous.read_text() == "original failure\n"
    log.write_text("")
    module.rotate_log(log, maximum_bytes=1)
    assert previous.read_text() == "original failure\n"
    log.write_text("next failure\n")
    outside = tmp_path / "outside"
    outside.write_text("keep\n")
    linked = tmp_path / "service.log.2"
    linked.symlink_to(outside)
    with pytest.raises((ValueError, RuntimeError), match="unsafe|owner|regular"):
        module.rotate_log(log, maximum_bytes=1)
    assert log.read_text() == "next failure\n"
    assert previous.read_text() == "original failure\n"
    assert outside.read_text() == "keep\n"


@pytest.mark.parametrize("enabled,skip", [(False, "0"), (True, "1")])
def test_headless_refresh_preserves_explicit_login_preference(tmp_path: Path, enabled: bool, skip: str) -> None:
    config = tmp_path / "helper-config.json"
    config.write_text(json.dumps({"launchAtLogin": enabled}))
    result = shell(shell_function(INSTALLER, "select_helper_agent_path") + r'''
resolve_repo_python() { printf '%s\n' "$PYTHON"; }
HELPER_CONFIG_FILE="$CONFIG"
LAUNCH_AGENT_PLIST="$SUPPORT/persistent.plist"
APP_SUPPORT_DIR="$SUPPORT"
SKIP_LOGIN_ITEM="$SKIP"
select_helper_agent_path
printf '%s\n%s\n' "$HELPER_LOGIN_PREFERENCE" "$HELPER_SELECTED_AGENT_PLIST"
''', PYTHON=sys.executable, CONFIG=str(config), SUPPORT=str(tmp_path), SKIP=skip)
    assert result.returncode == 0, result.stderr
    selected = tmp_path / ("persistent.plist" if enabled else "runtime/helper-supervisor.plist")
    assert result.stdout.splitlines() == [str(enabled).lower(), str(selected)]


@pytest.mark.parametrize("foreign", [False, True])
def test_helper_registration_refuses_a_foreign_loaded_job(tmp_path: Path, foreign: bool) -> None:
    executable = "/Applications/Viventium.app/Contents/MacOS/ViventiumHelper"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    launchctl = fake_bin / "launchctl"
    program = "/Applications/Other.app/Contents/MacOS/Other" if foreign else executable
    launchctl.write_text("#!/bin/sh\nprintf '%s\\n' 'program = " + program + "'\n")
    launchctl.chmod(0o755)
    config = tmp_path / "helper-config.json"
    config.write_text(json.dumps({"repoRoot": str(tmp_path), "appSupportDir": str(tmp_path)}))
    result = shell(shell_function(INSTALLER, "verify_helper_supervisor_binding") + r'''
resolve_repo_python() { printf '%s\n' "$PYTHON"; }
HELPER_CONFIG_FILE="$CONFIG"
HELPER_RUNTIME_REPO_ROOT="$SUPPORT"
APP_SUPPORT_DIR="$SUPPORT"
HELPER_APP_BUNDLE=/Applications/Viventium.app
HELPER_EXECUTABLE_NAME=ViventiumHelper
LAUNCH_AGENT_PLIST="$SUPPORT/persistent.plist"
verify_helper_supervisor_binding
''', PYTHON=sys.executable, CONFIG=str(config), SUPPORT=str(tmp_path), PATH=str(fake_bin) + ":" + os.environ["PATH"])
    assert result.returncode == (1 if foreign else 0), result.stderr
    assert ("Refusing unrelated loaded helper supervisor" in result.stderr) == foreign
    assert not (tmp_path / "persistent.plist").exists()
    assert not (tmp_path / "runtime/helper-supervisor.plist").exists()


def test_intent_config_and_lock_reject_links_without_touching_targets(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location("helper_runtime_intent", ROOT / "scripts/viventium/helper_runtime_intent.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    config = tmp_path / "helper-config.json"
    config.write_text('{"runtimeSupervision":{"desiredState":"running"}}\n')
    original = config.read_bytes()
    duplicate = tmp_path / "hardlink"
    os.link(config, duplicate)
    with pytest.raises(module.HelperIntentError, match="owner-controlled"):
        module.update_runtime_intent(config, "stopped")
    assert duplicate.read_bytes() == original
    duplicate.unlink()
    lock = tmp_path / ".helper-config.json.lock"
    lock.unlink()
    target = tmp_path / "external-lock"
    target.write_text("keep\n")
    lock.symlink_to(target)
    with pytest.raises(module.HelperIntentError, match="lock is unsafe"):
        module.update_runtime_intent(config, "stopped")
    assert config.read_bytes() == original
    assert target.read_text() == "keep\n"


def test_packaged_native_intent_uses_fresh_binding_revision_and_preferences(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.syspath_prepend(str(ROOT / "scripts/viventium"))
    spec = importlib.util.spec_from_file_location("native_intent_contract", ROOT / "scripts/viventium/native_runtime.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    config = {"repoRoot": "/public/release", "appSupportDir": str(tmp_path), "nativeRuntime": True,
              "runtimeSupervision": {"desiredState": "running"}}
    path = tmp_path / "helper-config.json"
    path.write_text(json.dumps({**config, "futurePreference": "newer"}))
    path.chmod(0o600)
    module.set_helper_desired_state(tmp_path, config, "stopped")
    stopped = json.loads(path.read_text())
    assert stopped["futurePreference"] == "newer"
    assert stopped["runtimeSupervision"]["desiredState"] == "stopped"
    revision = stopped["runtimeSupervision"]["intentRevision"]
    module.set_helper_desired_state(tmp_path, config, "running")
    assert json.loads(path.read_text())["runtimeSupervision"]["intentRevision"] != revision
    latest = json.loads(path.read_text())
    latest["repoRoot"] = "/public/other-release"
    path.write_text(json.dumps(latest))
    before = path.read_bytes()
    with pytest.raises(module.RuntimeError_, match="saved state was preserved"):
        module.set_helper_desired_state(tmp_path, config, "stopped")
    assert path.read_bytes() == before
    assert '"helper_runtime_intent.py"' in (ROOT / "scripts/viventium/assemble_native_payload.py").read_text()


@pytest.mark.parametrize("writer", ["installer", "visibility"])
def test_installer_binding_write_waits_for_shared_intent_lock_and_reads_fresh(tmp_path: Path, writer: str) -> None:
    import fcntl
    import time
    path = tmp_path / "helper-config.json"
    path.write_text(json.dumps({"repoRoot": "/public/prior", "appSupportDir": str(tmp_path),
                                "runtimeSupervision": {"desiredState": "running"}}))
    lock = tmp_path / ".helper-config.json.lock"
    with lock.open("w") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        script = shell_function(INSTALLER, "write_helper_config") + r'''
resolve_repo_python() { printf '%s\n' "$PYTHON"; }
HELPER_CONFIG_FILE="$CONFIG"
HELPER_RUNTIME_REPO_ROOT=/public/current
APP_SUPPORT_DIR="$SUPPORT"
HELPER_RUNTIME_ALLOW_PROTECTED=0
SCRIPT_DIR="$SCRIPTS"
write_helper_config
'''
        if writer == "visibility":
            script = shell_function(CLI, "set_helper_status_bar_visibility") + r'''
helper_config_file() { printf '%s\n' "$CONFIG"; }
resolve_helper_runtime_repo_root() { printf /public/current; }
active_runtime_checkout_allows_repo_root() { return 1; }
refresh_repo_python() { :; }
PYTHON_BIN="$PYTHON"
REPO_ROOT="$SCRIPTS/../.."
APP_SUPPORT_DIR="$SUPPORT"
set_helper_status_bar_visibility 0
'''
        process = subprocess.Popen(["bash", "-c", "set -euo pipefail\n" + script], stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, env={**os.environ, "PYTHON": sys.executable,
                                   "CONFIG": str(path), "SUPPORT": str(tmp_path), "SCRIPTS": str(ROOT / "scripts/viventium")})
        try:
            time.sleep(0.15)
            assert process.poll() is None, "Installer must acquire the same lock before reading intent"
            path.write_text(json.dumps({"repoRoot": "/public/prior", "appSupportDir": str(tmp_path),
                                        "runtimeSupervision": {"desiredState": "stopped", "intentRevision": "new-stop"}}))
            fcntl.flock(held, fcntl.LOCK_UN)
            stdout, stderr = process.communicate(timeout=10)
            assert process.returncode == 0, stderr
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()
    saved = json.loads(path.read_text())
    assert saved["repoRoot"] == "/public/current"
    assert saved["runtimeSupervision"] == {"desiredState": "stopped", "intentRevision": "new-stop"}


def test_managed_log_refusal_uses_private_bounded_alternate_but_not_unsafe_parent(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location("native_log_contract", ROOT / "scripts/viventium/native_runtime.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    root = tmp_path / "logs"
    root.mkdir()
    original = root / "service.log"
    evidence = root / "evidence"
    original.write_text("failure evidence\n")
    os.link(original, evidence)
    selected = module.prepare_runtime_log(original, maximum_bytes=1)
    assert selected == root / "service.recovery.log"
    assert selected.stat().st_mode & 0o777 == 0o600
    selected.write_text("recovery failure\n")
    assert module.prepare_runtime_log(original, maximum_bytes=1) == selected
    assert (root / "service.recovery.log.1").read_text() == "recovery failure\n"
    assert evidence.read_text() == original.read_text() == "failure evidence\n"
    external = tmp_path / "external"
    external.mkdir()
    linked_parent = tmp_path / "linked"
    linked_parent.symlink_to(external, target_is_directory=True)
    with pytest.raises(module.RuntimeError_, match="parent is unsafe"):
        module.prepare_runtime_log(linked_parent / "service.log")
    assert not list(external.iterdir())


def test_helper_io_recovery_requires_fresh_trusted_same_running_intent(tmp_path: Path) -> None:
    source = HELPER.read_text()
    definitions = "enum RuntimeDesiredState:" + source.split("enum RuntimeDesiredState:", 1)[1].split("private struct ActiveRuntimeCheckout:", 1)[0]
    body = r'''
let url = URL(fileURLWithPath: CommandLine.arguments[1])
var original = HelperConfig(repoRoot: "/public/viventium", appSupportDir: url.deletingLastPathComponent().path, runtimeSupervision: .defaultRunning)
original.runtimeSupervision!.requestRunning()
try HelperConfigPreservingStore.save(config: original, to: url, supervisionWrite: .explicitIntent)
precondition(HelperConfigPreservingStore.confirmsCurrentRunningIntent(original, at: url))
let directory = url.deletingLastPathComponent()
try FileManager.default.setAttributes([.posixPermissions: 0o500], ofItemAtPath: directory.path)
var observation = original
observation.runtimeSupervision!.recordLaunchAttempt(at: Date(), baseDelay: 15, maximumDelay: 900)
let failed = HelperConfigPreservingStore.result(config: observation, to: url, supervisionWrite: .observed)
try FileManager.default.setAttributes([.posixPermissions: 0o700], ofItemAtPath: directory.path)
precondition(failed == .unavailable)
precondition(HelperConfigPreservingStore.confirmsCurrentRunningIntent(observation, at: url))
var stop = original
stop.runtimeSupervision!.requestStopped()
try HelperConfigPreservingStore.save(config: stop, to: url, supervisionWrite: .explicitIntent)
precondition(!HelperConfigPreservingStore.confirmsCurrentRunningIntent(observation, at: url))
let stale = HelperConfigPreservingStore.result(config: observation, to: url, supervisionWrite: .observed)
precondition(stale == .staleIntent)
try FileManager.default.removeItem(at: url)
let target = directory.appendingPathComponent("target.json")
try JSONEncoder().encode(original).write(to: target)
try FileManager.default.createSymbolicLink(at: url, withDestinationURL: target)
precondition(!HelperConfigPreservingStore.confirmsCurrentRunningIntent(observation, at: url))
precondition(HelperConfigPreservingStore.result(config: observation, to: url, supervisionWrite: .observed) == .unsafePath)
print("io-authority-ok")
'''
    assert "io-authority-ok" in swift_run(tmp_path, definitions, body)
    refresh = source.split("private func refreshRuntimeDesiredState()", 1)[1].split("private func reconcileRuntimeSupervision", 1)[0]
    assert "supervision.intentRevision != config.runtimeSupervision?.intentRevision" in refresh
    assert "supervision != self.runtimeSupervision" not in refresh, "Unsaved IO backoff cannot be reset by unchanged durable bookkeeping"


@pytest.mark.parametrize("ownership,installs", [("owned", True), ("not-owned", False), ("unknown", False)])
def test_missing_helper_is_only_restored_for_owned_install(tmp_path: Path, ownership: str, installs: bool) -> None:
    result = shell(shell_function(CLI, "launch_macos_helper_app") + r'''
uname() { echo Darwin; }
read_install_helper_ownership() { printf '%s\n' "$OWNERSHIP"; }
run_macos_helper_install_command() { echo install; }
run_macos_helper_installer() { echo ensure; }
VIVENTIUM_HELPER_APP_BUNDLE="$MISSING"
launch_macos_helper_app
''', OWNERSHIP=ownership, MISSING=str(tmp_path / "missing.app"))
    assert result.returncode == (0 if installs else 1), result.stderr
    assert ("install" in result.stdout) == installs
    assert ("ensure" in result.stdout) == installs
    uninstall = CLI.read_text().rsplit("  uninstall-helper)", 1)[1].split("    ;;", 1)[0]
    assert uninstall.index('run_macos_helper_installer uninstall') < uninstall.index('write_install_ownership_receipt false')


def test_helper_io_failure_submits_one_bounded_recovery_but_stop_blocks_next(tmp_path: Path) -> None:
    source = HELPER.read_text()
    definitions = "enum RuntimeDesiredState:" + source.split("enum RuntimeDesiredState:", 1)[1].split("private struct ActiveRuntimeCheckout:", 1)[0]
    persist = source.split("    private func persistRuntimeSupervision(", 1)[1].split("\n    private func log(", 1)[0]
    persist = "    @discardableResult func persistRuntimeSupervision(" + persist
    persist = persist.replace('FileManager.default.homeDirectoryForCurrentUser\n                .appendingPathComponent("Library/Application Support/Viventium/helper-config.json")',
                              'URL(fileURLWithPath: config.appSupportDir).appendingPathComponent("config.json")')
    refresh = source.split("    private func refreshRuntimeDesiredState()", 1)[1].split("\n    private func reconcileRuntimeSupervision", 1)[0]
    refresh = "    func refreshRuntimeDesiredState()" + refresh
    definitions += r'''
private final class Probe {
    static var url: URL!
    var config: HelperConfig?
    var runtimeSupervision = RuntimeSupervisionState.defaultRunning
    static func saveConfigResult(_ config: HelperConfig, supervisionWrite: HelperSupervisionWrite) -> HelperConfigWriteResult { .unavailable }
    static func loadPersistedConfig() -> HelperConfig? { HelperConfigPreservingStore.loadOwnerControlledConfig(at: url) }
    func cancelStackLaunch() {}
    func log(_ text: String) {}
''' + persist + refresh + "\n}\n"
    body = r'''
let url = URL(fileURLWithPath: CommandLine.arguments[1])
var config = HelperConfig(repoRoot: "/public/viventium", appSupportDir: url.deletingLastPathComponent().path, runtimeSupervision: .defaultRunning)
config.runtimeSupervision!.requestRunning()
try HelperConfigPreservingStore.save(config: config, to: url, supervisionWrite: .explicitIntent)
Probe.url = url
let probe = Probe(); probe.config = config; probe.runtimeSupervision = config.runtimeSupervision!
let now = Date()
probe.runtimeSupervision.recordLaunchAttempt(at: now, baseDelay: 15, maximumDelay: 900)
var submissions = 0
if probe.persistRuntimeSupervision() { submissions += 1 }
probe.refreshRuntimeDesiredState()
precondition(!probe.runtimeSupervision.shouldLaunch(at: now.addingTimeInterval(1)))
precondition(submissions == 1)
config.runtimeSupervision!.requestStopped()
try HelperConfigPreservingStore.save(config: config, to: url, supervisionWrite: .explicitIntent)
probe.refreshRuntimeDesiredState()
if probe.runtimeSupervision.desiredState == .running && probe.persistRuntimeSupervision() { submissions += 1 }
precondition(probe.runtimeSupervision.desiredState == .stopped)
precondition(submissions == 1)
print("bounded-io-launch-ok")
'''
    assert "bounded-io-launch-ok" in swift_run(tmp_path, definitions, body)


@pytest.mark.parametrize("persistent,expected", [(True, "true"), (False, "unknown")])
def test_missing_login_field_migrates_only_known_registration(tmp_path: Path, persistent: bool, expected: str) -> None:
    config = tmp_path / "helper-config.json"
    config.write_text('{}\n')
    agent = tmp_path / "persistent.plist"
    if persistent:
        agent.write_text("synthetic existing registration\n")
    script = shell_function(INSTALLER, "select_helper_agent_path") + shell_function(INSTALLER, "persist_helper_login_preference") + r'''
resolve_repo_python() { printf '%s\n' "$PYTHON"; }
HELPER_CONFIG_FILE="$CONFIG"
LAUNCH_AGENT_PLIST="$SUPPORT/persistent.plist"
APP_SUPPORT_DIR="$SUPPORT"
SCRIPT_DIR="$SCRIPTS"
SKIP_LOGIN_ITEM=1
select_helper_agent_path
persist_helper_login_preference
printf '%s\n%s\n' "$HELPER_LOGIN_PREFERENCE" "$HELPER_SELECTED_AGENT_PLIST"
'''
    result = shell(script, PYTHON=sys.executable, CONFIG=str(config), SUPPORT=str(tmp_path), SCRIPTS=str(ROOT / "scripts/viventium"))
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines()[0] == expected
    saved = json.loads(config.read_text())
    if persistent:
        assert saved["launchAtLogin"] is True
        assert result.stdout.splitlines()[1] == str(agent)
    else:
        assert "launchAtLogin" not in saved
        assert result.stdout.splitlines()[1] == str(tmp_path / "runtime/helper-supervisor.plist")


def test_helper_rejected_config_has_typed_reason_and_visible_repair_state(tmp_path: Path) -> None:
    source = HELPER.read_text()
    definitions = "enum RuntimeDesiredState:" + source.split("enum RuntimeDesiredState:", 1)[1].split("private struct ActiveRuntimeCheckout:", 1)[0]
    body = r'''
let url = URL(fileURLWithPath: CommandLine.arguments[1])
let config = HelperConfig(repoRoot: "/public/viventium", appSupportDir: url.deletingLastPathComponent().path)
try HelperConfigPreservingStore.save(config: config, to: url)
precondition(try HelperConfigPreservingStore.readOwnerControlledConfig(at: url) == config)
func refused(_ expected: String) {
    do { _ = try HelperConfigPreservingStore.readOwnerControlledConfig(at: url); preconditionFailure("unsafe config accepted") }
    catch { precondition(String(describing: error) == expected) }
}
try FileManager.default.setAttributes([.posixPermissions: 0o660], ofItemAtPath: url.path)
refused("unsafeFile")
try FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: url.path)
let evidence = url.deletingLastPathComponent().appendingPathComponent("evidence")
try FileManager.default.linkItem(at: url, to: evidence)
refused("unsafeFile")
try FileManager.default.removeItem(at: evidence)
try FileManager.default.setAttributes([.posixPermissions: 0o770], ofItemAtPath: url.deletingLastPathComponent().path)
refused("unsafeDirectory")
try FileManager.default.setAttributes([.posixPermissions: 0o700], ofItemAtPath: url.deletingLastPathComponent().path)
try "invalid".write(to: url, atomically: true, encoding: .utf8)
refused("invalid")
try FileManager.default.removeItem(at: url)
refused("unavailable")
try FileManager.default.createSymbolicLink(at: url, withDestinationURL: evidence)
refused("unsafeFile")
print("config-repair-ok")
'''
    body = body.replace('precondition(try HelperConfigPreservingStore.readOwnerControlledConfig(at: url) == config)',
                        'let loaded = try HelperConfigPreservingStore.readOwnerControlledConfig(at: url); precondition(loaded == config)')
    assert "config-repair-ok" in swift_run(tmp_path, definitions, body)
    load = source.split("private static func loadConfig()", 1)[1].split("private static func saveConfigResult", 1)[0]
    assert 'Helper configuration needs repair: \\(error)' in load
    assert 'NSLog("%@", message)' in load
    refresh = source.split("private func refreshState(force: Bool = false)", 1)[1].split("if Self.configUsesProtectedRepoRoot", 1)[0]
    assert '.unavailable("Configuration needs repair")' in refresh

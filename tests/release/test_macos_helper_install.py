from __future__ import annotations

import os
import stat
import subprocess
import hashlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "viventium" / "install_macos_helper.sh"
FALLBACK_BUILD_SCRIPT = REPO_ROOT / "scripts" / "viventium" / "build_macos_helper_fallback.sh"
HELPER_SOURCE = (
    REPO_ROOT
    / "apps"
    / "macos"
    / "ViventiumHelper"
    / "Sources"
    / "ViventiumHelper"
    / "ViventiumHelperApp.swift"
)
HELPER_PACKAGE = REPO_ROOT / "apps" / "macos" / "ViventiumHelper" / "Package.swift"
HELPER_INFO_PLIST = (
    REPO_ROOT
    / "apps"
    / "macos"
    / "ViventiumHelper"
    / "Sources"
    / "ViventiumHelper"
    / "Resources"
    / "Info.plist"
)
PREBUILT_DIR = REPO_ROOT / "apps" / "macos" / "ViventiumHelper" / "prebuilt"
PREBUILT_EXECUTABLE = PREBUILT_DIR / "ViventiumHelper-universal"
PREBUILT_SOURCE_HASH = PREBUILT_DIR / "source.sha256"
BIN_VIVENTIUM = REPO_ROOT / "bin" / "viventium"


def _make_fake_executable(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def test_install_and_uninstall_helper_bundle(tmp_path: Path) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    fake_exec = tmp_path / "build" / "ViventiumHelper"
    _make_fake_executable(fake_exec)

    env = os.environ.copy()
    env.update(
        {
            "HOME": str(fake_home),
            "VIVENTIUM_HELPER_SKIP_BUILD": "1",
            "VIVENTIUM_HELPER_SKIP_LAUNCHCTL": "1",
            "VIVENTIUM_HELPER_SKIP_LOGIN_ITEM": "1",
            "VIVENTIUM_HELPER_BUILT_EXECUTABLE": str(fake_exec),
        }
    )
    app_support = fake_home / "Library" / "Application Support" / "Viventium"
    legacy_runner = app_support / "helper-scripts" / "helper-terminal-run.command"
    stale_detached_runner = app_support / "helper-scripts" / "helper-detached-start.pid.sh"
    legacy_launch_agent = fake_home / "Library" / "LaunchAgents" / "ai.viventium.helper.terminal.plist"
    zsh_history = fake_home / ".zsh_history"
    zsh_session_history = fake_home / ".zsh_sessions" / "legacy.history"
    terminal_saved_state = (
        fake_home / "Library" / "Saved Application State" / "com.apple.Terminal.savedState"
    )
    terminal_saved_state_file = terminal_saved_state / "windows.plist"
    legacy_runner.parent.mkdir(parents=True, exist_ok=True)
    legacy_runner.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    stale_detached_runner.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    legacy_launch_agent.parent.mkdir(parents=True, exist_ok=True)
    legacy_launch_agent.write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0">
<dict>
  <key>ProgramArguments</key>
  <array>
    <string>{legacy_runner}</string>
  </array>
</dict>
</plist>
""",
        encoding="utf-8",
    )
    zsh_history.write_text(
        "/usr/bin/true\n"
        f"{legacy_runner} ; exit;\n"
        f"{app_support / 'helper-scripts' / 'helper-detached-start.pid.command'} ; exit;\n",
        encoding="utf-8",
    )
    zsh_session_history.parent.mkdir(parents=True, exist_ok=True)
    zsh_session_history.write_text(
        f"{legacy_runner} ; exit;\n"
        "echo keep-me\n",
        encoding="utf-8",
    )
    terminal_saved_state_file.parent.mkdir(parents=True, exist_ok=True)
    terminal_saved_state_file.write_bytes(
        (
            "legacy terminal session\n"
            f"{legacy_runner}\n"
            f"{app_support / 'helper-scripts' / 'helper-detached-start.pid.command'}\n"
        ).encode("utf-8")
    )

    subprocess.run(
        [
            str(SCRIPT),
            "install",
            "--app-support-dir",
            str(app_support),
            "--repo-root",
            str(REPO_ROOT),
            "--no-launch",
        ],
        check=True,
        env=env,
    )

    app_bundle = fake_home / "Applications" / "Viventium.app"
    helper_config = app_support / "helper-config.json"
    stack_wrapper = app_support / "helper-scripts" / "viventium-stack.sh"

    assert (app_bundle / "Contents" / "MacOS" / "ViventiumHelper").exists()
    assert (app_bundle / "Contents" / "Info.plist").exists()
    assert (app_bundle / "Contents" / "Resources" / "Viventium.icns").exists()
    assert helper_config.exists()
    assert not legacy_runner.exists()
    assert not stale_detached_runner.exists()
    assert not legacy_launch_agent.exists()
    assert "helper-terminal-run.command" not in zsh_history.read_text(encoding="utf-8")
    assert "helper-detached-start.pid.command" not in zsh_history.read_text(encoding="utf-8")
    assert "helper-terminal-run.command" not in zsh_session_history.read_text(encoding="utf-8")
    assert "echo keep-me" in zsh_session_history.read_text(encoding="utf-8")
    assert not terminal_saved_state.exists()
    assert str(REPO_ROOT) in helper_config.read_text(encoding="utf-8")
    assert '"showInStatusBar": true' in helper_config.read_text(encoding="utf-8")
    assert stack_wrapper.exists()
    wrapper_text = stack_wrapper.read_text(encoding="utf-8")
    assert 'exec /bin/bash ' in wrapper_text
    assert '"$@"' in wrapper_text
    assert "export VIVENTIUM_HELPER_STOP_BACKGROUND_NATIVE=1" in wrapper_text
    assert "bin/viventium" in wrapper_text
    assert "--app-support-dir" in wrapper_text
    assert " stop " in wrapper_text
    assert " launch " in wrapper_text
    assert wrapper_text.index('if [[ "${1:-}" == "--stop" ]]; then') < wrapper_text.index(
        "export VIVENTIUM_HELPER_STOP_BACKGROUND_NATIVE=1"
    )

    subprocess.run(
        [
            str(SCRIPT),
            "uninstall",
            "--app-support-dir",
            str(app_support),
            "--repo-root",
            str(REPO_ROOT),
        ],
        check=True,
        env=env,
    )

    assert not app_bundle.exists()


def test_install_scrubs_shell_escaped_helper_history_entries(tmp_path: Path) -> None:
    fake_home = tmp_path / "home with spaces"
    fake_home.mkdir(parents=True)
    fake_exec = tmp_path / "build" / "ViventiumHelper"
    _make_fake_executable(fake_exec)

    env = os.environ.copy()
    env.update(
        {
            "HOME": str(fake_home),
            "VIVENTIUM_HELPER_SKIP_BUILD": "1",
            "VIVENTIUM_HELPER_SKIP_LAUNCHCTL": "1",
            "VIVENTIUM_HELPER_SKIP_LOGIN_ITEM": "1",
            "VIVENTIUM_HELPER_BUILT_EXECUTABLE": str(fake_exec),
        }
    )

    app_support = fake_home / "Library" / "Application Support" / "Viventium"
    zsh_history = fake_home / ".zsh_history"
    helper_dir = app_support / "helper-scripts"
    escaped_helper_dir = str(helper_dir).replace(" ", "\\ ")
    zsh_history.write_text(
        f"{escaped_helper_dir}/helper-detached-start.pid.command ; exit;\n"
        f"{escaped_helper_dir}/helper-terminal-run.command ; exit;\n"
        "echo keep-me\n",
        encoding="utf-8",
    )

    subprocess.run(
        [
            str(SCRIPT),
            "install",
            "--app-support-dir",
            str(app_support),
            "--repo-root",
            str(REPO_ROOT),
            "--no-launch",
        ],
        check=True,
        env=env,
    )

    history_text = zsh_history.read_text(encoding="utf-8")
    assert "helper-detached-start.pid.command" not in history_text
    assert "helper-terminal-run.command" not in history_text
    assert "echo keep-me" in history_text


def test_install_preserves_hidden_status_bar_preference(tmp_path: Path) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    fake_exec = tmp_path / "build" / "ViventiumHelper"
    _make_fake_executable(fake_exec)

    env = os.environ.copy()
    env.update(
        {
            "HOME": str(fake_home),
            "VIVENTIUM_HELPER_SKIP_BUILD": "1",
            "VIVENTIUM_HELPER_SKIP_LAUNCHCTL": "1",
            "VIVENTIUM_HELPER_SKIP_LOGIN_ITEM": "1",
            "VIVENTIUM_HELPER_BUILT_EXECUTABLE": str(fake_exec),
        }
    )

    app_support = fake_home / "Library" / "Application Support" / "Viventium"
    helper_config = app_support / "helper-config.json"
    helper_config.parent.mkdir(parents=True, exist_ok=True)
    helper_config.write_text(
        '{\n  "repoRoot": "/tmp/old",\n  "appSupportDir": "/tmp/old",\n  "showInStatusBar": false\n}\n',
        encoding="utf-8",
    )

    subprocess.run(
        [
            str(SCRIPT),
            "install",
            "--app-support-dir",
            str(app_support),
            "--repo-root",
            str(REPO_ROOT),
            "--no-launch",
        ],
        check=True,
        env=env,
    )

    config_text = helper_config.read_text(encoding="utf-8")
    assert str(REPO_ROOT) in config_text
    assert '"showInStatusBar": false' in config_text


def test_helper_source_autostarts_stack_on_launch() -> None:
    source = HELPER_SOURCE.read_text(encoding="utf-8")
    install_script = SCRIPT.read_text(encoding="utf-8")
    quit_section = source.split("func quit() {", 1)[1].split("private func activateHelperLifecycle", 1)[0]
    refresh_section = source.split("private func refreshState(force: Bool = false) {", 1)[1].split(
        "private func maybeAutoStartOnLaunch",
        1,
    )[0]

    assert 'self?.maybeAutoStartOnLaunch(trigger: "launch")' in source
    assert 'self?.maybeAutoStartOnLaunch(trigger: "poll")' in source
    assert "DispatchQueue.main.asyncAfter" in source
    assert "if Self.cliOperationStillRunning(appSupportDir: config.appSupportDir)" in source
    assert "let inFlightState = Self.inFlightStackState(appSupportDir: config.appSupportDir)" in source
    assert 'self.log("Auto-start launching stack' in source
    assert 'self.startStack(openWhenReady: false, launchReason: "auto-start:' in source
    assert 'return self.makeNamedHelperLogURL(appSupportDir: appSupportDir, logFileName: "viventium-helper.log")' in source
    assert 'private nonisolated static func makeNamedHelperLogURL(' in source
    assert 'process.arguments = ["\\(repoRoot)/bin/viventium", "--app-support-dir", appSupportDir] + arguments' in source
    assert "guard let detachedStartPID = Self.submitDetachedStart(" in source
    assert 'let startLogURL = Self.makeNamedHelperLogURL(' in source
    assert "let startLogOffset = Self.fileSize(startLogURL)" in source
    assert 'logFileName: "helper-start.log"' in source
    assert 'self.log("CLI detached start submission failed' in source
    assert 'self.log("CLI detached start submitted pid' in source
    assert 'private nonisolated static func submitDetachedStart(' in source
    assert 'private nonisolated static func submitDetachedStop(' in source
    assert 'private nonisolated static func submitDetachedHelperStackCommand(' in source
    assert "private nonisolated static func loopbackCandidateURLs(port: Int, path: String) -> [URL]" in source
    assert 'URL(string: "http://\\($0):\\(port)\\(path)")' in source
    assert 'guard let host = url.host, host == "localhost" || host == "127.0.0.1" else {' in source
    assert 'return ["localhost", "127.0.0.1"].compactMap { candidateHost in' in source
    assert "private nonisolated static func firstHTTPStatus(urls: [URL], timeoutInterval: TimeInterval = 1.5) async -> Int?" in source
    assert 'await self.firstHTTPStatus(urls: self.loopbackCandidateURLs(port: port, path: "/api/health"))' in source
    assert 'await self.firstHTTPStatus(urls: self.loopbackCandidateURLs(port: port, path: "/"))' in source
    assert "return await self.firstHTTPStatus(urls: self.candidateURLs(for: url)) != nil" in source
    assert 'pidFileName: "helper-detached-start.pid"' in source
    assert 'pidFileName: "helper-detached-stop.pid"' in source
    assert 'let stackScriptPath = self.helperStackScriptPath(appSupportDir: appSupportDir)' in source
    assert 'let runnerScriptURL = URL(fileURLWithPath: self.helperDetachedCommandScriptPath(' in source
    assert 'let legacyRunnerScriptURL = URL(fileURLWithPath: self.legacyHelperDetachedCommandScriptPath(' in source
    assert 'guard FileManager.default.isExecutableFile(atPath: stackScriptPath) else {' in source
    assert 'let escapedCommand = (["/bin/bash", stackScriptPath] + commandArguments)' in source
    assert 'let detachedCommand = """' in source
    assert 'cd \\(escapedAppSupportDir)' in source
    assert 'nohup \\(escapedCommand) >> \\(escapedLogPath) 2>&1 < /dev/null &' in source
    assert 'try? FileManager.default.removeItem(at: runnerScriptURL)' in source
    assert 'try? FileManager.default.removeItem(at: legacyRunnerScriptURL)' in source
    assert 'process.executableURL = URL(fileURLWithPath: "/bin/bash")' in source
    assert 'process.arguments = ["-lc", detachedCommand]' in source
    assert 'process.currentDirectoryURL = URL(fileURLWithPath: appSupportDir, isDirectory: true)' in source
    assert 'process.executableURL = URL(fileURLWithPath: "/usr/bin/open")' not in source
    assert '"-a", "Terminal"' not in source
    assert 'commandArguments: ["--stop"]' in source
    assert 'private nonisolated static func helperStackScriptPath(appSupportDir: String) -> String' in source
    assert 'private nonisolated static func helperDetachedCommandScriptPath(' in source
    assert 'private nonisolated static func legacyHelperDetachedCommandScriptPath(' in source
    assert '"\\(appSupportDir)/helper-scripts/viventium-stack.sh"' in source
    assert '"\\(appSupportDir)/helper-scripts/\\(pidFileName).sh"' in source
    assert '"\\(appSupportDir)/helper-scripts/\\(pidFileName).command"' in source
    assert "private nonisolated static func shellQuoted(_ value: String) -> String" in source
    assert "private nonisolated static func appleScriptQuoted(_ value: String) -> String" in source
    assert "private nonisolated static func pidFromFile(_ url: URL) -> Int32?" in source
    assert "private nonisolated static func pidIsRunning(_ pid: Int32) -> Bool" in source
    assert "private nonisolated static func terminatePIDIfNeeded(" in source
    assert 'logFileName: "helper-stop.log"' in source
    assert 'self.log("Quit requested; stopping stack before helper exit")' in source
    assert '@Published private(set) var showInStatusBarEnabled: Bool = true' in source
    assert "private var config: HelperConfig?" in source
    assert 'self.showInStatusBarEnabled = self.config?.showInStatusBar ?? true' in source
    assert "private func activateHelperLifecycle() {" in source
    assert "private func presentStatusBarRestorePrompt() {" in source
    assert "private static func saveConfig(_ config: HelperConfig) -> Bool" in source
    assert 'self?.presentStatusBarRestorePrompt()' in source
    assert 'self.log("Status-bar helper enabled")' in source
    assert 'self.log("Status-bar helper hidden")' in source
    assert 'Run `bin/viventium status-bar on` whenever you want to bring the menu-bar icon back.' in source
    assert "self.stopStack(terminateWhenDone: true)" in quit_section
    assert "NSApplication.shared.terminate(nil)" not in quit_section
    assert 'self.log("Quitting helper")' not in quit_section
    assert 'self.log("Helper exiting after stack stop")' in source
    assert 'Button("Quit") {' in source
    assert 'Button(self.controller.actionLabel) {' in source
    assert 'Button(self.controller.statusLabel) {}' in source
    assert "MenuBarExtra(" in source
    assert "isInserted: Binding(" in source
    assert "if self.controller.showsStatusRow {" in source
    assert '"Show in Status Bar"' in source
    assert 'set: { self.controller.setShowInStatusBar($0) }' in source
    assert '.disabled(self.controller.actionDisabled)' in source
    assert "private nonisolated static func launchCLIProcess(" in source
    assert "private nonisolated static func cliOperationCommand(appSupportDir: String) -> String?" in source
    assert "private nonisolated static func inFlightStackState(appSupportDir: String) -> StackState?" in source
    assert 'let commandPath = "\\(appSupportDir)/state/cli-operation.lock/command"' in source
    assert 'case "launch", "start":' in source
    assert 'case "stop":' in source
    assert "let process = self.makeCLIProcess(" in source
    assert "var environment = self.makeCLIEnvironment()" in source
    assert "process.currentDirectoryURL = URL(fileURLWithPath: repoRoot, isDirectory: true)" in source
    assert 'environment["PWD"] = repoRoot' in source
    assert "environmentOverrides" in source
    assert "process.standardInput = FileHandle.nullDevice" in source
    assert 'appendingPathComponent(logFileName)' in source
    assert "private nonisolated static func runCLI(" in source
    assert "private nonisolated static func fileSize(_ url: URL?) -> UInt64" in source
    assert "private nonisolated static func logSegment(_ url: URL?, offset: UInt64) -> String" in source
    assert (
        "private nonisolated static func launchFailureMarkerSeen(startLogURL: URL?, startLogOffset: UInt64) -> Bool"
        in source
    )
    assert "private nonisolated static func userFacingSurfaceHealthy(runtime: RuntimePorts) async -> Bool" in source
    assert "nonisolated static func stopCompletionReached(runtime: RuntimePorts, appSupportDir: String) async -> Bool" in source
    assert "nonisolated static func managedServicesRunning(runtime: RuntimePorts) async -> Bool" in source
    assert "nonisolated static func managedServicesHealthy(runtime: RuntimePorts) async -> Bool" in source
    assert "nonisolated static func endpointResponding(urlString: String) async -> Bool" in source
    assert "nonisolated static func stackOwnedByDifferentRepo(" in source
    assert "nonisolated static func loadStackOwnerState(appSupportDir: String, runtimeProfile: String) -> StackOwnerState?" in source
    assert "nonisolated static func telegramBridgeRunning(runtime: RuntimePorts, appSupportDir: String) -> Bool" in source
    assert "nonisolated static func pidFileProcessRunning(_ url: URL) -> Bool" in source
    assert 'self.log("Start blocked; another workspace owns the running stack")' in source
    assert 'self.log("Stop blocked; another workspace owns the running stack")' in source
    assert 'self.log("Auto-start blocked; split-workspace state detected' in source
    assert 'self.stackState = .unavailable("Split Workspace")' in source
    assert 'self.stackState = .running' in refresh_section
    assert 'self.stackState = .stopped' in refresh_section
    assert refresh_section.index("if splitWorkspace {") < refresh_section.index("if healthy {")
    assert refresh_section.index("if healthy {") < refresh_section.index("if shouldPreserveBusyState {")
    assert 'self.log("Auto-start skipped; stack already healthy' in source
    assert 'self.stackState = .running\n                    self.didAttemptLaunchAutostart = true' in source
    assert 'appendingPathComponent("state/runtime/\\(runtimeProfile)/stack-owner.json")' in source
    assert 'let managedStopCheckURLs: [String]' in source
    assert 'managedStopCheckURLs: self.managedStopCheckURLs(values: values)' in source
    assert "return await self.managedServicesHealthy(runtime: runtime)" in source
    assert 'if self.boolValue(values["START_SCHEDULING_MCP"])' in source
    assert 'if self.boolValue(values["START_GOOGLE_MCP"])' in source
    assert 'if self.boolValue(values["START_MS365_MCP"])' in source
    assert 'if self.boolValue(values["START_RAG_API"])' in source
    assert 'if self.boolValue(values["START_FIRECRAWL"])' in source
    assert 'if self.boolValue(values["START_SEARXNG"])' in source
    assert 'if self.boolValue(values["VIVENTIUM_VOICE_ENABLED"] ?? "true")' in source
    assert '"Built-in Viventium agent seeding failed"' in source
    assert '"Failed to seed built-in Viventium agents"' in source
    assert '"All services stopped."' in source
    assert 'private nonisolated static func defaultCLIPath(' in source
    assert 'private nonisolated static func makeCLIEnvironment()' in source
    assert '"/usr/bin"' in source
    assert '"/bin"' in source
    assert '"/usr/sbin"' in source
    assert '"/sbin"' in source
    assert "private let launchHealthTimeoutSeconds: Int = 1800" in source
    assert "private let stopHealthTimeoutSeconds: Int = 120" in source
    assert "private let postTimeoutStopGraceSeconds: Int = 30" in source
    assert "private let busyStateHandoffGraceSeconds: TimeInterval = 8" in source
    assert "private let delayedQuitWatchTimeoutSeconds: Int = 420" in source
    assert "private var busyStateGraceDeadline: Date?" in source
    assert "private var launchAtLoginRefreshTask: Task<Void, Never>?" in source
    assert "private func refreshLaunchAtLoginState(force: Bool = false) {" in source
    assert "self.refreshLaunchAtLoginState(force: force)" in source
    assert "self.launchAtLoginRefreshTask = Task.detached(priority: .utility)" in source
    assert "private nonisolated static func launchAtLoginFastPathEnabled() -> Bool" in source
    assert "self.launchAtLoginFastPathEnabled() || self.loginItemExists()" in source
    assert "timeoutSeconds: 5" in source
    assert 'self.launchAtLoginEnabled = Self.launchAtLoginIsEnabled()' not in refresh_section
    assert 'self.launchAtLoginEnabled = Self.launchAtLoginIsEnabled()' not in source
    assert "cleanup_legacy_terminal_helper_launchers()" in install_script
    assert '"showInStatusBar": bool(existing.get("showInStatusBar", True)),' in install_script
    assert 'helper_script_dir.glob("*.command")' in install_script
    assert 'helper-detached-start.pid.command' in install_script
    assert 'helper-detached-stop.pid.command' in install_script
    assert 'legacy_history_markers = tuple(' in install_script
    assert 'for history_path in (Path.home() / ".zsh_history",):' in install_script
    assert 'zsh_sessions_dir = Path.home() / ".zsh_sessions"' in install_script
    assert 'if history_path.suffix not in {".history", ".historynew", ".session"}:' in install_script
    assert "com.apple.Terminal.savedState" in install_script
    assert "terminal_saved_state_contains_legacy_marker" in install_script
    assert "shutil.rmtree(terminal_saved_state_dir, ignore_errors=True)" in install_script
    assert "allowEarlyFailure: true" in source
    assert "private struct StopCommandOutcome" in source
    assert "let commandBlockedByActiveOperation: Bool" in source
    assert "let stackStillRunningAfterGrace: Bool" in source
    assert "let stopOutcome = await Self.runStopCLIUntilStackStops(" in source
    assert "postTimeoutGraceSeconds: self.postTimeoutStopGraceSeconds" in source
    assert "commandTimedOut, stopOutcome.stackStopped" in source
    assert 'self.log("Stop blocked by another Viventium CLI operation")' in source
    assert 'self.log("Stop command hung after stack shutdown; helper forced it to end")' in source
    assert 'self.log("Stop command itself timed out before stack finished stopping")' in source
    assert 'self.log("Stop command exited, but Viventium was still stopping after the grace window")' in source
    assert 'self.log("Terminated lingering stop command after bounded wait")' in source
    assert 'self.log("Stop still converging; helper will keep watching and exit after stack stop")' in source
    assert 'self.log("Helper exiting after delayed stop completion")' in source
    assert "private nonisolated static func runStopCLIUntilStackStops(" in source
    assert "postTimeoutGraceSeconds: Int," in source
    assert "let stopLogURL = logFileName.map" in source
    assert "let stopLogOffset = self.fileSize(stopLogURL)" in source
    assert "guard let stopCommandPID = self.submitDetachedStop(" in source
    assert "let commandStillRunningAtDeadline = self.pidIsRunning(stopCommandPID)" in source
    assert "stackStoppedAfterGrace" in source
    assert "let stopLogSegment = self.logSegment(stopLogURL, offset: stopLogOffset)" in source
    assert 'stopLogSegment.contains("Another Viventium CLI operation is already running")' in source
    assert "commandBlockedByActiveOperation: commandBlockedByActiveOperation" in source
    assert "stackStillRunningAfterGrace: !stackStoppedAfterGrace && !commandStillRunningAtDeadline && !commandBlockedByActiveOperation" in source
    assert "waitForStoppedStack(" in source
    assert "private var delayedQuitWatchTask: Task<Void, Never>?" in source
    assert "self.cancelDelayedQuitWatch()" in source
    assert "private func cancelDelayedQuitWatch()" in source
    assert "private func beginDelayedQuitWatch(config: HelperConfig, runtime: RuntimePorts)" in source
    assert "timeoutSeconds: self.delayedQuitWatchTimeoutSeconds" in source
    assert 'let playgroundPort = Int(values["VIVENTIUM_PLAYGROUND_PORT"] ?? "") ?? 3300' in source
    assert 'let runtimeProfile = values["VIVENTIUM_RUNTIME_PROFILE"] ?? "isolated"' in source
    assert 'self.openURLString = Self.frontendURLString(host: host, port: runtime.frontendPort)' in source
    assert "let preferredOpenURLString = await Self.preferredOpenURLString(runtime: runtime, host: host)" in source
    assert "self.openURLString = preferredOpenURLString" in source
    assert "let playgroundPort: Int" in source
    assert "let runtimeProfile: String" in source
    assert 'appendingPathComponent("state/runtime/\\(runtime.runtimeProfile)", isDirectory: true)' in source
    assert 'let legacyLogRoot = runtimeRoot.appendingPathComponent("logs", isDirectory: true)' in source
    assert 'runtimeRoot.appendingPathComponent("telegram_bot.pid")' in source
    assert 'runtimeRoot.appendingPathComponent("telegram_codex.pid")' in source
    assert 'legacyLogRoot.appendingPathComponent("telegram_bot.pid")' in source
    assert 'legacyLogRoot.appendingPathComponent("telegram_codex.pid")' in source
    assert 'private nonisolated static func frontendURLString(host: String, port: Int) -> String' in source
    assert "private nonisolated static func preferredOpenURLString(runtime: RuntimePorts, host: String) async -> String" in source
    assert "return self.frontendURLString(host: host, port: runtime.playgroundPort)" in source
    assert "private nonisolated static func userFacingSurfaceHealthy(runtime: RuntimePorts) async -> Bool" in source
    assert "private nonisolated static func stackHealthy(apiPort: Int, frontendPort: Int, playgroundPort: Int) async -> Bool" in source
    assert "return await self.frontendHealthy(port: playgroundPort)" in source
    assert "guard await self.stackHealthy(" in source
    assert "playgroundPort: runtime.playgroundPort" in source
    assert "return await self.managedServicesHealthy(runtime: runtime)" in source
    assert "let shouldPreserveBusyState =" in source
    assert "self.stackState.actionBusy &&" in source
    assert "inFlightState != nil" in source
    assert "let busyStateGraceActive = (self.busyStateGraceDeadline ?? .distantPast) > Date()" in source
    assert "(inFlightState != nil || busyStateGraceActive)" in source
    assert "guard force || !self.stackState.actionBusy else {" not in source
    assert 'self.beginBusyState(.starting)' in source
    assert 'self.beginBusyState(.stopping)' in source
    assert "private func beginBusyState(_ state: StackState) {" in source
    assert "self.busyStateGraceDeadline = Date().addingTimeInterval(self.busyStateHandoffGraceSeconds)" in source
    assert 'case .starting:\n            return "Starting..."' in source
    assert 'case .stopping:\n            return "Stopping..."' in source
    assert "private nonisolated static func terminateProcessIfNeeded(" in source
    assert "Darwin.kill(process.processIdentifier, SIGTERM)" in source
    assert "Darwin.kill(process.processIdentifier, SIGKILL)" in source
    assert 'self.log("Stop did not complete cleanly; keeping helper open")' in source
    assert 'alert.messageText = "Viventium did not finish stopping"' in source
    assert "private nonisolated static func waitForStoppedStack(" in source
    assert 'alert.messageText = "Another Viventium workspace owns the running stack"' in source


def test_helper_package_stays_compatible_with_clean_intel_command_line_tools() -> None:
    package_source = HELPER_PACKAGE.read_text(encoding="utf-8")
    install_script = SCRIPT.read_text(encoding="utf-8")
    cli_source = BIN_VIVENTIUM.read_text(encoding="utf-8")
    register_section = install_script.split("register_login_item() {", 1)[1].split(
        "unregister_login_item() {",
        1,
    )[0]

    assert package_source.startswith("// swift-tools-version: 5.10")
    assert 'HELPER_PREBUILT_DIR="${VIVENTIUM_HELPER_PREBUILT_DIR:-$HELPER_PACKAGE_DIR/prebuilt}"' in install_script
    assert (
        'HELPER_PREBUILT_EXECUTABLE="${VIVENTIUM_HELPER_PREBUILT_EXECUTABLE:-$HELPER_PREBUILT_DIR/${HELPER_EXECUTABLE_NAME}-universal}"'
        in install_script
    )
    assert 'HELPER_PREBUILT_SOURCE_HASH_FILE="${VIVENTIUM_HELPER_PREBUILT_SOURCE_HASH_FILE:-$HELPER_PREBUILT_DIR/source.sha256}"' in install_script
    assert 'OSASCRIPT_TIMEOUT_SECONDS="${VIVENTIUM_HELPER_OSASCRIPT_TIMEOUT_SECONDS:-15}"' in install_script
    assert 'swiftpm_timeout_seconds="${VIVENTIUM_HELPER_SWIFTPM_TIMEOUT_SECONDS:-60}"' in install_script
    assert 'rm -f "$HELPER_PACKAGE_DIR/.build/workspace-state.json"' in install_script
    assert '["swift", "build", "-c", "release", "--product", helper_name],' in install_script
    assert 'sys.stderr.write(f"[viventium] SwiftPM helper build timed out after {timeout:.0f}s\\n")' in install_script
    assert 'echo "[viventium] SwiftPM helper build failed; retrying with direct swiftc compile" >&2' in install_script
    assert 'compile_timeout_seconds="${VIVENTIUM_HELPER_DIRECT_COMPILE_TIMEOUT_SECONDS:-600}"' in install_script
    assert 'swiftc_bin="$(xcrun --find swiftc)"' in install_script
    assert 'target_triple="$(uname -m)-apple-macosx13.0"' in install_script
    assert 'python_bin="$(resolve_repo_python)"' in install_script
    assert '"$python_bin" - "$compile_timeout_seconds" "$swiftc_bin" "$sdk_path" "$target_triple" \\' in install_script
    assert '"-parse-as-library",' in install_script
    assert 'sys.stderr.write(f"[viventium] Direct helper compile timed out after {timeout:.0f}s\\n")' in install_script
    assert 'helper_source_hash() {' in install_script
    assert 'prebuilt_helper_matches_sources() {' in install_script
    assert 'use_prebuilt_helper() {' in install_script
    assert 'if prebuilt_helper_matches_sources; then' in install_script
    assert 'echo "[viventium] Using prebuilt helper fallback from $HELPER_PREBUILT_EXECUTABLE" >&2' in install_script
    assert 'echo "[viventium] Prebuilt helper fallback exists but does not match current helper sources" >&2' in install_script
    assert 'echo "[viventium] No matching prebuilt helper fallback found" >&2' in install_script
    assert '"$HELPER_PACKAGE_DIR/Sources/ViventiumHelper/ViventiumHelperApp.swift"' in install_script
    assert 'export VIVENTIUM_HELPER_STOP_BACKGROUND_NATIVE=1' in install_script
    assert 'bin_viventium = repo_root / "bin" / "viventium"' in install_script
    assert 'if [[ "{dollar}{{1:-}}" == "--stop" ]]; then' in install_script
    assert 'exec /bin/bash {q(bin_viventium)} --app-support-dir {q(app_support_dir)} stop "{dollar}@"' in install_script
    assert 'export VIVENTIUM_DETACHED_START=true' in install_script
    assert 'exec /bin/bash {q(bin_viventium)} --app-support-dir {q(app_support_dir)} launch "{dollar}@"' in install_script
    assert install_script.index('if [[ "{dollar}{{1:-}}" == "--stop" ]]; then') < install_script.index(
        'export VIVENTIUM_HELPER_STOP_BACKGROUND_NATIVE=1'
    )
    assert '[[ "$SKIP_LOGIN_ITEM" == "1" ]] && return 1' in install_script
    assert '"$python_bin" - "$OSASCRIPT_TIMEOUT_SECONDS" "$HELPER_APP_BUNDLE" <<\'PY\'' in register_section
    assert "bundle_path = sys.argv[2]" in register_section
    assert 'path:"{bundle_path}"' in register_section
    assert 'path:"$HELPER_APP_BUNDLE"' not in register_section
    assert 'sys.stderr.write(f"[viventium] Login-item registration timed out after {timeout:.0f}s; falling back to LaunchAgent\\n")' in install_script
    assert '[[ "$LAUNCH_AFTER_INSTALL" == "1" ]] || return 0' in install_script
    assert 'helper_args+=(--no-launch)' in cli_source
    assert 'local defer_launch=0' in cli_source
    assert 'case "${1:-}" in' in cli_source
    assert '--no-launch)' in cli_source
    assert 'defer_launch=1' in cli_source
    assert 'if [[ "$defer_launch" == "1" || "${HEADLESS:-0}" == "1" || "${AUTO_START:-1}" != "1" ]]; then' in cli_source
    assert 'if [[ "${HEADLESS:-0}" == "1" ]]; then' in cli_source
    assert 'run_macos_helper_install_command() {' in cli_source
    assert 'if [[ "$#" -gt 0 ]]; then' in cli_source
    assert 'if [[ ${#helper_args[@]} -gt 0 ]]; then' in cli_source
    assert 'launch_macos_helper_app() {' in cli_source
    assert 'local helper_app_bundle="${VIVENTIUM_HELPER_APP_BUNDLE:-$HOME/Applications/Viventium.app}"' in cli_source
    assert '/usr/bin/open -g "$helper_app_bundle" >/dev/null 2>&1 || true' in cli_source
    assert 'if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then' in cli_source
    assert 'subcommand_usage install' in cli_source
    assert 'export VIVENTIUM_CLI_LOCK_HELD=0' in cli_source
    assert 'unset VIVENTIUM_CLI_LOCK_DIR' in cli_source
    assert 'if [[ "${VIVENTIUM_DETACHED_START:-false}" == "1" || "${VIVENTIUM_DETACHED_START:-false}" == "true" ]]; then' in cli_source
    assert 'Detached helper/app launches hand control off to the background runtime.' in cli_source
    assert 'cleanup_cli_lock' in cli_source.split('if [[ "${VIVENTIUM_DETACHED_START:-false}" == "1" || "${VIVENTIUM_DETACHED_START:-false}" == "true" ]]; then', 1)[1]
    assert 'VIVENTIUM_HELPER_SKIP_LOGIN_ITEM=1 run_macos_helper_installer install "$@"' in cli_source
    assert 'run_macos_helper_installer install' in cli_source
    assert 'if ! run_macos_helper_install_command 1 "${helper_args[@]}"; then' in cli_source
    assert 'if ! run_macos_helper_install_command 0 "${helper_args[@]}"; then' in cli_source
    assert 'maybe_install_macos_helper --no-launch' in cli_source
    assert 'stop_native_stack_detached() {' in cli_source
    assert 'VIVENTIUM_HELPER_STOP_BACKGROUND_NATIVE' in cli_source
    assert 'scripts", "viventium", "native_stack.sh"' in cli_source
    assert 'Native runtime cleanup continuing in background' in cli_source
    assert 'stack_owner_state_file() {' in cli_source
    assert 'write_stack_owner_state() {' in cli_source
    assert 'printf \'%s\\n\' "$APP_SUPPORT_DIR/state/runtime/${runtime_profile}/stack-owner.json"' in cli_source
    assert '"repoRoot": repo_root,' in cli_source
    assert 'write_stack_owner_state "$COMMAND"' in cli_source

    prebuilt_check_offset = install_script.index('if prebuilt_helper_matches_sources; then')
    direct_compile_offset = install_script.index(
        'echo "[viventium] SwiftPM helper build failed; retrying with direct swiftc compile" >&2'
    )
    assert prebuilt_check_offset < direct_compile_offset


def test_prebuilt_helper_fallback_matches_current_sources() -> None:
    assert FALLBACK_BUILD_SCRIPT.exists()
    assert PREBUILT_EXECUTABLE.exists()
    assert PREBUILT_EXECUTABLE.stat().st_size > 0
    assert PREBUILT_SOURCE_HASH.exists()

    digest = hashlib.sha256()
    for relative_path in (
        Path("Package.swift"),
        Path("Sources") / "ViventiumHelper" / "ViventiumHelperApp.swift",
        Path("Sources") / "ViventiumHelper" / "Resources" / "Info.plist",
    ):
        digest.update(relative_path.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update((HELPER_PACKAGE.parent / relative_path).read_bytes())
        digest.update(b"\0")

    actual_hash = digest.hexdigest()
    expected_hash = PREBUILT_SOURCE_HASH.read_text(encoding="utf-8").strip()

    assert actual_hash == expected_hash

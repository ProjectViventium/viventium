import AppKit
import Darwin
import Foundation
import SwiftUI

private struct HelperConfig: Codable {
    let repoRoot: String
    let appSupportDir: String
    var showInStatusBar: Bool?
}

private struct StackOwnerState: Decodable {
    let repoRoot: String
}

private struct StopCommandOutcome {
    let stackStopped: Bool
    let commandLaunchFailed: Bool
    let commandTimedOut: Bool
    let commandBlockedByActiveOperation: Bool
    let stackStillRunningAfterGrace: Bool
    let commandExitStatus: Int32?
    let terminatedLingeringCommand: Bool
}

enum StackState: Equatable {
    case running
    case stopped
    case starting
    case stopping
    case unavailable(String)

    var menuLabel: String {
        switch self {
        case .running:
            return "Running"
        case .stopped:
            return "Stopped"
        case .starting:
            return "Starting..."
        case .stopping:
            return "Stopping..."
        case let .unavailable(message):
            return message
        }
    }

    var actionLabel: String {
        switch self {
        case .running:
            return "Stop"
        case .stopped, .unavailable:
            return "Start"
        case .starting:
            return "Starting..."
        case .stopping:
            return "Stopping..."
        }
    }

    var actionBusy: Bool {
        switch self {
        case .starting, .stopping:
            return true
        default:
            return false
        }
    }
}

@MainActor
final class HelperController: ObservableObject {
    @Published private(set) var stackState: StackState = .stopped {
        didSet {
            if !self.stackState.actionBusy {
                self.busyStateGraceDeadline = nil
            }
        }
    }
    @Published private(set) var openURLString: String = "http://localhost:3190"
    @Published private(set) var launchAtLoginEnabled: Bool = false
    @Published private(set) var showInStatusBarEnabled: Bool = true

    private var config: HelperConfig?
    private let helperLogURL: URL?
    private var timer: Timer?
    private let envParser = RuntimeEnvParser()
    private let launchDate = Date()
    private let autoStartRetryWindowSeconds: TimeInterval = 45
    private let launchHealthTimeoutSeconds: Int = 1800
    private let stopHealthTimeoutSeconds: Int = 120
    private let postTimeoutStopGraceSeconds: Int = 30
    private let busyStateHandoffGraceSeconds: TimeInterval = 8
    // Heavy local stacks can legitimately take several minutes to drain all owned sidecars
    // after the initial bounded stop command has returned.
    private let delayedQuitWatchTimeoutSeconds: Int = 420
    private var didAttemptLaunchAutostart = false
    private var delayedQuitWatchTask: Task<Void, Never>?
    private var busyStateGraceDeadline: Date?
    private var activatedHelperLifecycle = false

    init() {
        self.config = Self.loadConfig()
        self.helperLogURL = Self.makeHelperLogURL(appSupportDir: self.config?.appSupportDir)
        self.launchAtLoginEnabled = Self.launchAtLoginIsEnabled()
        self.showInStatusBarEnabled = self.config?.showInStatusBar ?? true
        self.log("Helper launched")
        if self.showInStatusBarEnabled {
            self.activateHelperLifecycle()
        } else {
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) { [weak self] in
                Task { @MainActor in
                    self?.presentStatusBarRestorePrompt()
                }
            }
        }
    }

    var actionLabel: String {
        self.stackState.actionLabel
    }

    var statusLabel: String {
        self.stackState.menuLabel
    }

    var actionDisabled: Bool {
        self.stackState.actionBusy || self.config == nil
    }

    var showsStatusRow: Bool {
        !self.stackState.actionBusy
    }

    func setShowInStatusBar(_ enabled: Bool) {
        guard var config else {
            let alert = NSAlert()
            alert.messageText = "Missing helper config"
            alert.informativeText = "Reinstall the Viventium helper from this checkout, then try again."
            alert.alertStyle = .warning
            alert.addButton(withTitle: "OK")
            alert.runModal()
            return
        }
        guard enabled != self.showInStatusBarEnabled else {
            return
        }

        config.showInStatusBar = enabled
        guard Self.saveConfig(config) else {
            let alert = NSAlert()
            alert.messageText = "Could not update the status-bar setting"
            alert.informativeText = "Viventium could not save the helper preference. Please try again."
            alert.alertStyle = .warning
            alert.addButton(withTitle: "OK")
            alert.runModal()
            return
        }

        self.config = config
        self.showInStatusBarEnabled = enabled

        if enabled {
            self.log("Status-bar helper enabled")
            self.activateHelperLifecycle()
            return
        }

        self.log("Status-bar helper hidden")
        self.timer?.invalidate()
        self.timer = nil
        self.cancelDelayedQuitWatch()
        Task.detached(priority: .utility) {
            let updated = Self.setLaunchAtLoginEnabled(false)
            await MainActor.run {
                self.launchAtLoginEnabled = updated
                let alert = NSAlert()
                alert.messageText = "Viventium is hidden from the status bar"
                alert.informativeText = "Run `bin/viventium status-bar on` whenever you want to bring the menu-bar icon back."
                alert.alertStyle = .informational
                alert.addButton(withTitle: "OK")
                alert.runModal()
                NSApplication.shared.terminate(nil)
            }
        }
    }

    func setLaunchAtLogin(_ enabled: Bool) {
        Task.detached(priority: .utility) {
            let updated = Self.setLaunchAtLoginEnabled(enabled)
            await MainActor.run {
                self.launchAtLoginEnabled = updated
                if updated != enabled {
                    let alert = NSAlert()
                    alert.messageText = "Could not update Start at Login"
                    alert.informativeText = "macOS did not accept the helper login-item change. You can retry from the menu."
                    alert.alertStyle = .warning
                    alert.addButton(withTitle: "OK")
                    alert.runModal()
                }
            }
        }
    }

    func openViventium() {
        switch self.stackState {
        case .running:
            self.openBrowser()
        case .starting, .stopping:
            return
        case .stopped, .unavailable:
            let alert = NSAlert()
            alert.messageText = "Viventium is not running"
            alert.informativeText = "Start Viventium now and open it in your browser?"
            alert.alertStyle = .informational
            alert.addButton(withTitle: "Start and Open")
            alert.addButton(withTitle: "Cancel")
            let response = alert.runModal()
            if response == .alertFirstButtonReturn {
                self.startStack(openWhenReady: true)
            }
        }
    }

    func toggleStack() {
        switch self.stackState {
        case .running:
            self.stopStack()
        case .stopped, .unavailable:
            self.startStack(openWhenReady: false)
        case .starting, .stopping:
            return
        }
    }

    func quit() {
        self.log("Quit requested; stopping stack before helper exit")
        self.stopStack(terminateWhenDone: true)
    }

    private func activateHelperLifecycle() {
        guard !self.activatedHelperLifecycle else {
            return
        }
        self.activatedHelperLifecycle = true
        self.refreshState(force: true)
        self.timer = Timer.scheduledTimer(withTimeInterval: 4.0, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.refreshState()
                self?.maybeAutoStartOnLaunch(trigger: "poll")
            }
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.75) { [weak self] in
            Task { @MainActor in
                self?.maybeAutoStartOnLaunch(trigger: "launch")
            }
        }
    }

    private func presentStatusBarRestorePrompt() {
        let alert = NSAlert()
        alert.messageText = "Show Viventium in the status bar?"
        alert.informativeText = "The Viventium helper is currently hidden. Show it again now?"
        alert.alertStyle = .informational
        alert.addButton(withTitle: "Show")
        alert.addButton(withTitle: "Quit")
        if alert.runModal() == .alertFirstButtonReturn {
            self.setShowInStatusBar(true)
        } else {
            NSApplication.shared.terminate(nil)
        }
    }

    private func startStack(openWhenReady: Bool, launchReason: String = "manual") {
        self.cancelDelayedQuitWatch()
        guard let config else {
            self.log("Start requested without helper config")
            self.stackState = .unavailable("Missing helper config")
            return
        }
        self.log("Starting stack (\(launchReason))")
        self.beginBusyState(.starting)
        Task.detached(priority: .userInitiated) {
            let runtime = RuntimeEnvParser().readRuntime(appSupportDir: config.appSupportDir)
            if await Self.stackOwnedByDifferentRepo(
                runtime: runtime,
                appSupportDir: config.appSupportDir,
                expectedRepoRoot: config.repoRoot
            ) {
                await MainActor.run {
                    self.log("Start blocked; another workspace owns the running stack")
                    self.stackState = .unavailable("Split Workspace")
                    let alert = NSAlert()
                    alert.messageText = "Another Viventium workspace owns the running stack"
                    alert.informativeText = "Reinstall the helper from the active checkout or stop that stack from its own workspace before starting here."
                    alert.alertStyle = .warning
                    alert.addButton(withTitle: "OK")
                    alert.runModal()
                }
                return
            }
            let startLogURL = Self.makeNamedHelperLogURL(
                appSupportDir: config.appSupportDir,
                logFileName: "helper-start.log"
            )
            let startLogOffset = Self.fileSize(startLogURL)
            guard let detachedStartPID = Self.submitDetachedStart(
                appSupportDir: config.appSupportDir,
                logFileName: "helper-start.log"
            ) else {
                await MainActor.run {
                    self.log("CLI detached start submission failed (\(launchReason))")
                    self.refreshState(force: true)
                    self.log("Stack did not become healthy after \(launchReason)")
                    if openWhenReady {
                        let alert = NSAlert()
                            alert.messageText = "Viventium did not finish starting"
                        alert.informativeText = "Check Docker Desktop and the Viventium logs, then try again."
                        alert.alertStyle = .warning
                        alert.addButton(withTitle: "OK")
                        alert.runModal()
                    }
                }
                return
            }
            await MainActor.run {
                self.log("CLI detached start submitted pid \(detachedStartPID) (\(launchReason))")
            }
            let started: Bool
            started = await Self.waitForHealthyStack(
                runtime: runtime,
                appSupportDir: config.appSupportDir,
                timeoutSeconds: self.launchHealthTimeoutSeconds,
                allowEarlyFailure: true,
                startLogURL: startLogURL,
                startLogOffset: startLogOffset
            )
            await MainActor.run {
                self.refreshState(force: true)
                self.log(started ? "Stack healthy after \(launchReason)" : "Stack did not become healthy after \(launchReason)")
                if started && openWhenReady {
                    self.openBrowser()
                } else if openWhenReady && !started {
                    let alert = NSAlert()
                    alert.messageText = "Viventium did not finish starting"
                    alert.informativeText = "Check Docker Desktop and the Viventium logs, then try again."
                    alert.alertStyle = .warning
                    alert.addButton(withTitle: "OK")
                    alert.runModal()
                }
            }
        }
    }

    private func stopStack(terminateWhenDone: Bool = false) {
        if !terminateWhenDone {
            self.cancelDelayedQuitWatch()
        }
        guard let config else {
            self.log("Stop requested without helper config")
            self.stackState = .unavailable("Missing helper config")
            if terminateWhenDone {
                NSApplication.shared.terminate(nil)
            }
            return
        }
        self.log(terminateWhenDone ? "Stopping stack before helper exit" : "Stopping stack")
        self.beginBusyState(.stopping)
        Task.detached(priority: .userInitiated) {
            let runtime = RuntimeEnvParser().readRuntime(appSupportDir: config.appSupportDir)
            if await Self.stackOwnedByDifferentRepo(
                runtime: runtime,
                appSupportDir: config.appSupportDir,
                expectedRepoRoot: config.repoRoot
            ) {
                await MainActor.run {
                    self.log("Stop blocked; another workspace owns the running stack")
                    self.stackState = .unavailable("Split Workspace")
                    let alert = NSAlert()
                    alert.messageText = "Another Viventium workspace owns the running stack"
                    alert.informativeText = "This helper is attached to a different checkout, so Stop/Quit is intentionally blocked until the workspace binding is repaired."
                    alert.alertStyle = .warning
                    alert.addButton(withTitle: "OK")
                    alert.runModal()
                }
                return
            }
            let stopOutcome = await Self.runStopCLIUntilStackStops(
                repoRoot: config.repoRoot,
                appSupportDir: config.appSupportDir,
                runtime: runtime,
                timeoutSeconds: self.stopHealthTimeoutSeconds,
                postTimeoutGraceSeconds: self.postTimeoutStopGraceSeconds,
                logFileName: "helper-stop.log"
            )
            await MainActor.run {
                self.refreshState(force: true)
                if stopOutcome.commandLaunchFailed {
                    self.log("Stop command failed to launch")
                } else if stopOutcome.commandBlockedByActiveOperation {
                    self.log("Stop blocked by another Viventium CLI operation")
                } else if stopOutcome.commandTimedOut, stopOutcome.stackStopped {
                    self.log("Stop command hung after stack shutdown; helper forced it to end")
                } else if stopOutcome.commandTimedOut {
                    self.log("Stop command itself timed out before stack finished stopping")
                } else if stopOutcome.stackStillRunningAfterGrace {
                    self.log("Stop command exited, but Viventium was still stopping after the grace window")
                } else if let exitStatus = stopOutcome.commandExitStatus, exitStatus != 0 {
                    self.log("Stop command exited with status \(exitStatus)")
                }
                if stopOutcome.terminatedLingeringCommand {
                    self.log("Terminated lingering stop command after bounded wait")
                }
                if terminateWhenDone {
                    if stopOutcome.stackStopped {
                        self.cancelDelayedQuitWatch()
                        self.log("Helper exiting after stack stop")
                        NSApplication.shared.terminate(nil)
                    } else {
                        self.log("Stop still converging; helper will keep watching and exit after stack stop")
                        self.beginDelayedQuitWatch(config: config, runtime: runtime)
                    }
                }
            }
        }
    }

    private func cancelDelayedQuitWatch() {
        self.delayedQuitWatchTask?.cancel()
        self.delayedQuitWatchTask = nil
    }

    private func beginDelayedQuitWatch(config: HelperConfig, runtime: RuntimePorts) {
        self.cancelDelayedQuitWatch()
        self.delayedQuitWatchTask = Task { [weak self] in
            guard let self else {
                return
            }
            let stackStopped = await Self.waitForStoppedStack(
                runtime: runtime,
                appSupportDir: config.appSupportDir,
                frontendPort: runtime.frontendPort,
                timeoutSeconds: self.delayedQuitWatchTimeoutSeconds
            )
            guard !Task.isCancelled else {
                return
            }
            self.delayedQuitWatchTask = nil
            self.refreshState(force: true)
            if stackStopped {
                self.log("Helper exiting after delayed stop completion")
                NSApplication.shared.terminate(nil)
            } else {
                self.log("Stop did not complete cleanly; keeping helper open")
                let alert = NSAlert()
                alert.messageText = "Viventium did not finish stopping"
                alert.informativeText = "The helper stayed open so you can inspect logs and try stopping again."
                alert.alertStyle = .warning
                alert.addButton(withTitle: "OK")
                alert.runModal()
            }
        }
    }

    private func refreshState(force: Bool = false) {
        guard let config else {
            self.stackState = .unavailable("Missing helper config")
            return
        }
        let runtime = self.envParser.readRuntime(appSupportDir: config.appSupportDir)
        let host = LocalNetworkAddressResolver.currentHost() ?? "localhost"
        self.openURLString = Self.frontendURLString(host: host, port: runtime.frontendPort)
        self.launchAtLoginEnabled = Self.launchAtLoginIsEnabled()

        let allowBusyStateTransition = force
        Task {
            let preferredOpenURLString = await Self.preferredOpenURLString(runtime: runtime, host: host)
            let healthy = await Self.userFacingSurfaceHealthy(runtime: runtime)
            let splitWorkspace = await Self.stackOwnedByDifferentRepo(
                runtime: runtime,
                appSupportDir: config.appSupportDir,
                expectedRepoRoot: config.repoRoot
            )
            self.openURLString = preferredOpenURLString
            let inFlightState = Self.inFlightStackState(appSupportDir: config.appSupportDir)
            let busyStateGraceActive = (self.busyStateGraceDeadline ?? .distantPast) > Date()
            let shouldPreserveBusyState =
                !allowBusyStateTransition &&
                self.stackState.actionBusy &&
                (inFlightState != nil || busyStateGraceActive)
            if splitWorkspace {
                self.stackState = .unavailable("Split Workspace")
                return
            }
            if healthy {
                self.stackState = .running
                return
            }
            if shouldPreserveBusyState {
                return
            }
            if !healthy, let inFlightState {
                self.stackState = inFlightState
                return
            }
            self.stackState = .stopped
        }
    }

    private func beginBusyState(_ state: StackState) {
        self.stackState = state
        self.busyStateGraceDeadline = Date().addingTimeInterval(self.busyStateHandoffGraceSeconds)
    }

    private func maybeAutoStartOnLaunch(trigger: String) {
        guard !self.didAttemptLaunchAutostart else {
            return
        }
        guard let config else {
            self.log("Auto-start skipped; missing helper config")
            self.didAttemptLaunchAutostart = true
            return
        }
        if Date().timeIntervalSince(self.launchDate) > self.autoStartRetryWindowSeconds {
            self.log("Auto-start window expired before a launch attempt")
            self.didAttemptLaunchAutostart = true
            return
        }

        Task.detached(priority: .utility) {
            let runtime = RuntimeEnvParser().readRuntime(appSupportDir: config.appSupportDir)
            if await Self.stackOwnedByDifferentRepo(
                runtime: runtime,
                appSupportDir: config.appSupportDir,
                expectedRepoRoot: config.repoRoot
            ) {
                await MainActor.run {
                    self.log("Auto-start blocked; split-workspace state detected (\(trigger))")
                    self.stackState = .unavailable("Split Workspace")
                    self.didAttemptLaunchAutostart = true
                }
                return
            }
            if await Self.userFacingSurfaceHealthy(runtime: runtime) {
                await MainActor.run {
                    self.log("Auto-start skipped; stack already healthy (\(trigger))")
                    self.stackState = .running
                    self.didAttemptLaunchAutostart = true
                }
                return
            }
            if Self.cliOperationStillRunning(appSupportDir: config.appSupportDir) {
                await MainActor.run {
                    self.log("Auto-start deferred; CLI operation already running (\(trigger))")
                }
                return
            }

            await MainActor.run {
                guard !self.stackState.actionBusy else {
                    self.log("Auto-start deferred; helper busy as \(self.statusLabel) (\(trigger))")
                    return
                }
                self.didAttemptLaunchAutostart = true
                self.log("Auto-start launching stack (\(trigger))")
                self.startStack(openWhenReady: false, launchReason: "auto-start:\(trigger)")
            }
        }
    }

    private func log(_ message: String) {
        Self.appendHelperLog(self.helperLogURL, message)
    }

    private static func loadConfig() -> HelperConfig? {
        let configURL = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Application Support/Viventium/helper-config.json")
        guard
            let data = try? Data(contentsOf: configURL),
            let decoded = try? JSONDecoder().decode(HelperConfig.self, from: data)
        else {
            return nil
        }
        return decoded
    }

    private static func saveConfig(_ config: HelperConfig) -> Bool {
        let configURL = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Application Support/Viventium/helper-config.json")
        guard let data = try? JSONEncoder().encode(config) else {
            return false
        }
        do {
            try FileManager.default.createDirectory(
                at: configURL.deletingLastPathComponent(),
                withIntermediateDirectories: true,
                attributes: nil
            )
            try data.write(to: configURL, options: .atomic)
            return true
        } catch {
            return false
        }
    }

    private nonisolated static func makeHelperLogURL(appSupportDir: String?) -> URL? {
        guard let appSupportDir else {
            return nil
        }
        return self.makeNamedHelperLogURL(appSupportDir: appSupportDir, logFileName: "viventium-helper.log")
    }

    private nonisolated static func makeNamedHelperLogURL(appSupportDir: String, logFileName: String) -> URL {
        let logDir = URL(fileURLWithPath: appSupportDir, isDirectory: true)
            .appendingPathComponent("logs", isDirectory: true)
        try? FileManager.default.createDirectory(at: logDir, withIntermediateDirectories: true)
        return logDir.appendingPathComponent(logFileName)
    }

    private nonisolated static func appendHelperLog(_ url: URL?, _ message: String) {
        guard let url, let data = "[\(ISO8601DateFormatter().string(from: Date()))] \(message)\n".data(using: .utf8) else {
            return
        }
        if !FileManager.default.fileExists(atPath: url.path) {
            try? data.write(to: url, options: .atomic)
            return
        }
        guard let handle = try? FileHandle(forWritingTo: url) else {
            try? data.write(to: url, options: .atomic)
            return
        }
        defer {
            try? handle.close()
        }
        _ = try? handle.seekToEnd()
        try? handle.write(contentsOf: data)
    }

    private nonisolated static func loopbackCandidateURLs(port: Int, path: String) -> [URL] {
        let hosts = ["localhost", "127.0.0.1"]
        return hosts.compactMap { URL(string: "http://\($0):\(port)\(path)") }
    }

    private nonisolated static func candidateURLs(for url: URL) -> [URL] {
        guard let host = url.host, host == "localhost" || host == "127.0.0.1" else {
            return [url]
        }

        return ["localhost", "127.0.0.1"].compactMap { candidateHost in
            guard var components = URLComponents(url: url, resolvingAgainstBaseURL: false) else {
                return nil
            }
            components.host = candidateHost
            return components.url
        }
    }

    private nonisolated static func firstHTTPStatus(urls: [URL], timeoutInterval: TimeInterval = 1.5) async -> Int? {
        for url in urls {
            var request = URLRequest(url: url)
            request.httpMethod = "GET"
            request.timeoutInterval = timeoutInterval
            do {
                let (_, response) = try await URLSession.shared.data(for: request)
                if let http = response as? HTTPURLResponse {
                    return http.statusCode
                }
            } catch {
                continue
            }
        }
        return nil
    }

    private nonisolated static func apiHealthy(port: Int) async -> Bool {
        guard let status = await self.firstHTTPStatus(urls: self.loopbackCandidateURLs(port: port, path: "/api/health")) else {
            return false
        }
        return status == 200
    }

    private nonisolated static func frontendHealthy(port: Int) async -> Bool {
        guard let status = await self.firstHTTPStatus(urls: self.loopbackCandidateURLs(port: port, path: "/")) else {
            return false
        }
        return (200..<400).contains(status)
    }

    private nonisolated static func stackHealthy(apiPort: Int, frontendPort: Int, playgroundPort: Int) async -> Bool {
        let apiReady = await self.apiHealthy(port: apiPort)
        guard apiReady else {
            return false
        }
        let frontendReady = await self.frontendHealthy(port: frontendPort)
        guard frontendReady else {
            return false
        }
        // Voice-call deep links land on the dedicated modern playground, so the helper must
        // require that surface too before it reports Viventium as healthy.
        return await self.frontendHealthy(port: playgroundPort)
    }

    private nonisolated static func frontendURLString(host: String, port: Int) -> String {
        "http://\(host):\(port)"
    }

    private nonisolated static func preferredOpenURLString(runtime: RuntimePorts, host: String) async -> String {
        if await self.stackHealthy(
            apiPort: runtime.apiPort,
            frontendPort: runtime.frontendPort,
            playgroundPort: runtime.playgroundPort
        ) {
            return self.frontendURLString(host: host, port: runtime.frontendPort)
        }
        if await self.frontendHealthy(port: runtime.playgroundPort) {
            return self.frontendURLString(host: host, port: runtime.playgroundPort)
        }
        return self.frontendURLString(host: host, port: runtime.frontendPort)
    }

    private nonisolated static func userFacingSurfaceHealthy(runtime: RuntimePorts) async -> Bool {
        guard await self.stackHealthy(
            apiPort: runtime.apiPort,
            frontendPort: runtime.frontendPort,
            playgroundPort: runtime.playgroundPort
        ) else {
            return false
        }
        return await self.managedServicesHealthy(runtime: runtime)
    }

    private nonisolated static func waitForHealthyStack(
        runtime: RuntimePorts,
        appSupportDir: String,
        timeoutSeconds: Int,
        allowEarlyFailure: Bool,
        startLogURL: URL? = nil,
        startLogOffset: UInt64 = 0
    ) async -> Bool {
        let deadline = Date().addingTimeInterval(TimeInterval(timeoutSeconds))
        let earlyFailureDeadline = Date().addingTimeInterval(8)
        while Date() < deadline {
            if await self.userFacingSurfaceHealthy(runtime: runtime) {
                return true
            }
            if allowEarlyFailure,
               Date() >= earlyFailureDeadline,
               !self.cliOperationStillRunning(appSupportDir: appSupportDir),
               self.launchFailureMarkerSeen(startLogURL: startLogURL, startLogOffset: startLogOffset)
            {
                return false
            }
            try? await Task.sleep(for: .seconds(2))
        }
        return false
    }

    private nonisolated static func waitForStoppedStack(
        runtime: RuntimePorts,
        appSupportDir: String,
        frontendPort: Int,
        timeoutSeconds: Int
    ) async -> Bool {
        let deadline = Date().addingTimeInterval(TimeInterval(timeoutSeconds))
        while Date() < deadline {
            if await self.stopCompletionReached(runtime: runtime, appSupportDir: appSupportDir) {
                return true
            }
            try? await Task.sleep(for: .seconds(1))
        }
        return await self.stopCompletionReached(runtime: runtime, appSupportDir: appSupportDir)
    }

    private nonisolated static func runStopCLIUntilStackStops(
        repoRoot: String,
        appSupportDir: String,
        runtime: RuntimePorts,
        timeoutSeconds: Int,
        postTimeoutGraceSeconds: Int,
        logFileName: String? = nil
    ) async -> StopCommandOutcome {
        let stopLogURL = logFileName.map {
            self.makeNamedHelperLogURL(appSupportDir: appSupportDir, logFileName: $0)
        }
        let stopLogOffset = self.fileSize(stopLogURL)
        guard let stopCommandPID = self.submitDetachedStop(
            appSupportDir: appSupportDir,
            logFileName: logFileName ?? "helper-stop.log"
        ) else {
            return StopCommandOutcome(
                stackStopped: false,
                commandLaunchFailed: true,
                commandTimedOut: false,
                commandBlockedByActiveOperation: false,
                stackStillRunningAfterGrace: false,
                commandExitStatus: nil,
                terminatedLingeringCommand: false
            )
        }
        let deadline = Date().addingTimeInterval(TimeInterval(timeoutSeconds))
        while Date() < deadline {
            if await self.stopCompletionReached(runtime: runtime, appSupportDir: appSupportDir) {
                let terminatedLingeringCommand = await self.terminatePIDIfNeeded(stopCommandPID, graceSeconds: 10)
                return StopCommandOutcome(
                    stackStopped: true,
                    commandLaunchFailed: false,
                    commandTimedOut: false,
                    commandBlockedByActiveOperation: false,
                    stackStillRunningAfterGrace: false,
                    commandExitStatus: nil,
                    terminatedLingeringCommand: terminatedLingeringCommand
                )
            }
            let stopLogSegment = self.logSegment(stopLogURL, offset: stopLogOffset)
            if stopLogSegment.contains("Another Viventium CLI operation is already running") {
                break
            }
            if !self.pidIsRunning(stopCommandPID) {
                break
            }
            try? await Task.sleep(for: .seconds(1))
        }

        let stackStopped = await self.stopCompletionReached(runtime: runtime, appSupportDir: appSupportDir)
        let commandStillRunningAtDeadline = self.pidIsRunning(stopCommandPID)
        let terminatedLingeringCommand = await self.terminatePIDIfNeeded(stopCommandPID, graceSeconds: 2)
        let stackStoppedAfterGrace: Bool
        if !stackStopped && postTimeoutGraceSeconds > 0 {
            stackStoppedAfterGrace = await self.waitForStoppedStack(
                runtime: runtime,
                appSupportDir: appSupportDir,
                frontendPort: runtime.frontendPort,
                timeoutSeconds: postTimeoutGraceSeconds
            )
        } else {
            stackStoppedAfterGrace = stackStopped
        }
        let stopLogSegment = self.logSegment(stopLogURL, offset: stopLogOffset)
        let commandBlockedByActiveOperation =
            stopLogSegment.contains("Another Viventium CLI operation is already running")
        return StopCommandOutcome(
            stackStopped: stackStoppedAfterGrace,
            commandLaunchFailed: false,
            commandTimedOut: commandStillRunningAtDeadline,
            commandBlockedByActiveOperation: commandBlockedByActiveOperation,
            stackStillRunningAfterGrace: !stackStoppedAfterGrace && !commandStillRunningAtDeadline && !commandBlockedByActiveOperation,
            commandExitStatus: nil,
            terminatedLingeringCommand: terminatedLingeringCommand
        )
    }

    private nonisolated static func pidIsRunning(_ pid: Int32) -> Bool {
        guard pid > 0 else {
            return false
        }
        return Darwin.kill(pid, 0) == 0
    }

    private nonisolated static func terminatePIDIfNeeded(
        _ pid: Int32,
        graceSeconds: TimeInterval
    ) async -> Bool {
        guard self.pidIsRunning(pid) else {
            return false
        }

        Darwin.kill(pid, SIGTERM)
        let deadline = Date().addingTimeInterval(graceSeconds)
        while self.pidIsRunning(pid), Date() < deadline {
            try? await Task.sleep(for: .milliseconds(200))
        }

        guard self.pidIsRunning(pid) else {
            return true
        }

        Darwin.kill(pid, SIGKILL)
        return true
    }

    private nonisolated static func terminateProcessIfNeeded(
        _ process: Process,
        graceSeconds: TimeInterval
    ) async -> Bool {
        guard process.isRunning else {
            return false
        }

        Darwin.kill(process.processIdentifier, SIGTERM)
        let termDeadline = Date().addingTimeInterval(graceSeconds)
        while process.isRunning, Date() < termDeadline {
            try? await Task.sleep(for: .milliseconds(250))
        }
        if !process.isRunning {
            return true
        }

        Darwin.kill(process.processIdentifier, SIGKILL)
        let killDeadline = Date().addingTimeInterval(2)
        while process.isRunning, Date() < killDeadline {
            try? await Task.sleep(for: .milliseconds(100))
        }
        return true
    }

    private nonisolated static func fileSize(_ url: URL?) -> UInt64 {
        guard let url,
              let attributes = try? FileManager.default.attributesOfItem(atPath: url.path),
              let size = attributes[.size] as? NSNumber
        else {
            return 0
        }
        return size.uint64Value
    }

    private nonisolated static func launchFailureMarkerSeen(startLogURL: URL?, startLogOffset: UInt64) -> Bool {
        let segment = self.logSegment(startLogURL, offset: startLogOffset)
        guard !segment.isEmpty else {
            return false
        }
        let failureMarkers = [
            "Built-in Viventium agent seeding failed",
            "Failed to seed built-in Viventium agents",
            "All services stopped.",
        ]

        return failureMarkers.contains { segment.contains($0) }
    }

    private nonisolated static func logSegment(_ url: URL?, offset: UInt64) -> String {
        guard let url,
              let handle = try? FileHandle(forReadingFrom: url)
        else {
            return ""
        }

        defer {
            try? handle.close()
        }

        if offset > 0 {
            try? handle.seek(toOffset: offset)
        }

        guard
            let data = try? handle.readToEnd(),
            let segment = String(data: data, encoding: .utf8)
        else {
            return ""
        }
        return segment
    }

    private nonisolated static func cliOperationStillRunning(appSupportDir: String) -> Bool {
        let pidPath =
            "\(appSupportDir)/state/cli-operation.lock/pid"
        guard
            let raw = try? String(contentsOfFile: pidPath, encoding: .utf8),
            let pid = Int32(raw.trimmingCharacters(in: .whitespacesAndNewlines)),
            pid > 0
        else {
            return false
        }
        return kill(pid, 0) == 0
    }

    private nonisolated static func cliOperationCommand(appSupportDir: String) -> String? {
        guard self.cliOperationStillRunning(appSupportDir: appSupportDir) else {
            return nil
        }
        let commandPath = "\(appSupportDir)/state/cli-operation.lock/command"
        guard
            let command = (try? String(contentsOfFile: commandPath, encoding: .utf8))?
                .trimmingCharacters(in: .whitespacesAndNewlines),
            !command.isEmpty
        else {
            return nil
        }
        return command
    }

    private nonisolated static func inFlightStackState(appSupportDir: String) -> StackState? {
        switch self.cliOperationCommand(appSupportDir: appSupportDir) {
        case "launch", "start":
            return .starting
        case "stop":
            return .stopping
        default:
            return nil
        }
    }

    private nonisolated static func defaultCLIPath(homeDirectory: String, inheritedPath: String?) -> String {
        let candidates = [
            "/opt/homebrew/bin",
            "/opt/homebrew/sbin",
            "/usr/local/bin",
            "/usr/local/sbin",
            "/usr/bin",
            "/bin",
            "/usr/sbin",
            "/sbin",
            "/opt/homebrew/opt/node@20/bin",
            "/usr/local/opt/node@20/bin",
            "/opt/homebrew/opt/python@3.12/libexec/bin",
            "/usr/local/opt/python@3.12/libexec/bin",
            "/Applications/Docker.app/Contents/Resources/bin",
            "/Applications/Docker.app/Contents/MacOS",
            "\(homeDirectory)/Applications/Docker.app/Contents/Resources/bin",
            "\(homeDirectory)/Applications/Docker.app/Contents/MacOS",
        ]

        var seen = Set<String>()
        var ordered: [String] = []

        for entry in candidates + (inheritedPath?.split(separator: ":").map(String.init) ?? []) {
            let trimmed = entry.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !trimmed.isEmpty, !seen.contains(trimmed) else {
                continue
            }
            seen.insert(trimmed)
            ordered.append(trimmed)
        }

        return ordered.joined(separator: ":")
    }

    private nonisolated static func makeCLIEnvironment() -> [String: String] {
        let inherited = ProcessInfo.processInfo.environment
        let homeDirectory = FileManager.default.homeDirectoryForCurrentUser.path
        let userName = inherited["USER"] ?? inherited["LOGNAME"] ?? NSUserName()
        var environment: [String: String] = [
            "HOME": homeDirectory,
            "USER": userName,
            "LOGNAME": inherited["LOGNAME"] ?? userName,
            "SHELL": inherited["SHELL"] ?? "/bin/zsh",
            "TMPDIR": inherited["TMPDIR"] ?? NSTemporaryDirectory(),
            "PATH": self.defaultCLIPath(homeDirectory: homeDirectory, inheritedPath: inherited["PATH"]),
            "LANG": inherited["LANG"] ?? "C.UTF-8",
            "LC_ALL": inherited["LC_ALL"] ?? inherited["LANG"] ?? "C.UTF-8",
            "LC_CTYPE": inherited["LC_CTYPE"] ?? inherited["LANG"] ?? "C.UTF-8",
        ]

        if let sshAuthSock = inherited["SSH_AUTH_SOCK"], !sshAuthSock.isEmpty {
            environment["SSH_AUTH_SOCK"] = sshAuthSock
        }

        return environment
    }

    private nonisolated static func launchAgentPlistURL() -> URL {
        FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/LaunchAgents/ai.viventium.helper.plist")
    }

    private nonisolated static func runSystemProcess(
        executableURL: URL,
        arguments: [String],
        standardInput: String? = nil
    ) -> (status: Int32, stdout: String, stderr: String) {
        let process = Process()
        process.executableURL = executableURL
        process.arguments = arguments

        let stdoutPipe = Pipe()
        let stderrPipe = Pipe()
        process.standardOutput = stdoutPipe
        process.standardError = stderrPipe

        if let standardInput {
            let stdinPipe = Pipe()
            process.standardInput = stdinPipe
            if let data = standardInput.data(using: .utf8) {
                stdinPipe.fileHandleForWriting.write(data)
            }
            try? stdinPipe.fileHandleForWriting.close()
        }

        do {
            try process.run()
            process.waitUntilExit()
        } catch {
            return (1, "", String(describing: error))
        }

        let stdoutData = try? stdoutPipe.fileHandleForReading.readToEnd()
        let stderrData = try? stderrPipe.fileHandleForReading.readToEnd()
        return (
            process.terminationStatus,
            String(data: stdoutData ?? Data(), encoding: .utf8) ?? "",
            String(data: stderrData ?? Data(), encoding: .utf8) ?? ""
        )
    }

    private nonisolated static func loginItemExists() -> Bool {
        let script = """
        tell application "System Events"
          return exists login item "Viventium"
        end tell
        """
        let result = self.runSystemProcess(
            executableURL: URL(fileURLWithPath: "/usr/bin/osascript"),
            arguments: [],
            standardInput: script
        )
        guard result.status == 0 else {
            return false
        }
        return result.stdout.trimmingCharacters(in: .whitespacesAndNewlines) == "true"
    }

    private nonisolated static func launchAtLoginIsEnabled() -> Bool {
        self.loginItemExists() || FileManager.default.fileExists(atPath: self.launchAgentPlistURL().path)
    }

    private nonisolated static func removeLaunchAgent() {
        let plistURL = self.launchAgentPlistURL()
        _ = self.runSystemProcess(
            executableURL: URL(fileURLWithPath: "/bin/launchctl"),
            arguments: ["bootout", "gui/\(getuid())", plistURL.path]
        )
        try? FileManager.default.removeItem(at: plistURL)
    }

    private nonisolated static func unregisterLoginItem() {
        let script = """
        tell application "System Events"
          if exists login item "Viventium" then
            delete login item "Viventium"
          end if
        end tell
        """
        _ = self.runSystemProcess(
            executableURL: URL(fileURLWithPath: "/usr/bin/osascript"),
            arguments: [],
            standardInput: script
        )
    }

    private nonisolated static func registerLoginItem() -> Bool {
        let escapedBundlePath = Bundle.main.bundlePath
            .replacingOccurrences(of: "\\", with: "\\\\")
            .replacingOccurrences(of: "\"", with: "\\\"")
        let script = """
        tell application "System Events"
          if exists login item "Viventium" then
            delete login item "Viventium"
          end if
          make login item at end with properties {name:"Viventium", path:"\(escapedBundlePath)", hidden:true}
        end tell
        """
        let result = self.runSystemProcess(
            executableURL: URL(fileURLWithPath: "/usr/bin/osascript"),
            arguments: [],
            standardInput: script
        )
        return result.status == 0
    }

    private nonisolated static func setLaunchAtLoginEnabled(_ enabled: Bool) -> Bool {
        if enabled {
            return self.registerLoginItem()
        }

        self.unregisterLoginItem()
        self.removeLaunchAgent()
        return self.launchAtLoginIsEnabled() == false
    }

    private nonisolated static func makeCLIProcess(
        repoRoot: String,
        appSupportDir: String,
        arguments: [String],
        logFileName: String? = nil,
        environmentOverrides: [String: String] = [:]
    ) -> Process {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/bin/bash")
        process.currentDirectoryURL = URL(fileURLWithPath: repoRoot, isDirectory: true)
        process.arguments = ["\(repoRoot)/bin/viventium", "--app-support-dir", appSupportDir] + arguments
        var environment = self.makeCLIEnvironment()
        environment["PWD"] = repoRoot
        for (key, value) in environmentOverrides {
            environment[key] = value
        }
        process.environment = environment
        process.standardInput = FileHandle.nullDevice

        if let logFileName {
            let logDir = URL(fileURLWithPath: appSupportDir, isDirectory: true)
                .appendingPathComponent("logs", isDirectory: true)
            try? FileManager.default.createDirectory(at: logDir, withIntermediateDirectories: true)
            let logURL = logDir.appendingPathComponent(logFileName)
            if !FileManager.default.fileExists(atPath: logURL.path) {
                FileManager.default.createFile(atPath: logURL.path, contents: Data())
            }
            if let handle = try? FileHandle(forWritingTo: logURL) {
                _ = try? handle.seekToEnd()
                process.standardOutput = handle
                process.standardError = handle
            }
        }

        return process
    }

    private nonisolated static func launchCLIProcess(
        repoRoot: String,
        appSupportDir: String,
        arguments: [String],
        logFileName: String? = nil,
        environmentOverrides: [String: String] = [:]
    ) -> Process? {
        let process = self.makeCLIProcess(
            repoRoot: repoRoot,
            appSupportDir: appSupportDir,
            arguments: arguments,
            logFileName: logFileName,
            environmentOverrides: environmentOverrides
        )

        do {
            try process.run()
            return process
        } catch {
            return nil
        }
    }

    private nonisolated static func submitDetachedStart(
        appSupportDir: String,
        logFileName: String
    ) -> Int32? {
        self.submitDetachedHelperStackCommand(
            appSupportDir: appSupportDir,
            logFileName: logFileName,
            pidFileName: "helper-detached-start.pid",
            commandArguments: []
        )
    }

    private nonisolated static func submitDetachedStop(
        appSupportDir: String,
        logFileName: String,
    ) -> Int32? {
        self.submitDetachedHelperStackCommand(
            appSupportDir: appSupportDir,
            logFileName: logFileName,
            pidFileName: "helper-detached-stop.pid",
            commandArguments: ["--stop"]
        )
    }

    private nonisolated static func submitDetachedHelperStackCommand(
        appSupportDir: String,
        logFileName: String,
        pidFileName: String,
        commandArguments: [String]
    ) -> Int32? {
        let stackScriptPath = self.helperStackScriptPath(appSupportDir: appSupportDir)
        guard FileManager.default.isExecutableFile(atPath: stackScriptPath) else {
            return nil
        }
        let logPath = Self.makeNamedHelperLogURL(appSupportDir: appSupportDir, logFileName: logFileName).path
        let pidFileURL = URL(fileURLWithPath: appSupportDir, isDirectory: true)
            .appendingPathComponent("runtime/\(pidFileName)")
        let runnerScriptURL = URL(fileURLWithPath: self.helperDetachedCommandScriptPath(
            appSupportDir: appSupportDir,
            pidFileName: pidFileName
        ))
        let legacyRunnerScriptURL = URL(fileURLWithPath: self.legacyHelperDetachedCommandScriptPath(
            appSupportDir: appSupportDir,
            pidFileName: pidFileName
        ))
        try? FileManager.default.createDirectory(
            at: pidFileURL.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        try? FileManager.default.createDirectory(
            at: runnerScriptURL.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        try? FileManager.default.removeItem(at: pidFileURL)
        try? FileManager.default.removeItem(at: runnerScriptURL)
        try? FileManager.default.removeItem(at: legacyRunnerScriptURL)
        let escapedAppSupportDir = self.shellQuoted(appSupportDir)
        let escapedLogPath = self.shellQuoted(logPath)
        let escapedPidPath = self.shellQuoted(pidFileURL.path)
        let escapedCommand = (["/bin/bash", stackScriptPath] + commandArguments)
            .map(self.shellQuoted)
            .joined(separator: " ")
        let detachedCommand = """
set -euo pipefail
cd \(escapedAppSupportDir)
nohup \(escapedCommand) >> \(escapedLogPath) 2>&1 < /dev/null &
pid=$!
printf '%s\\n' "$pid" > \(escapedPidPath)
"""

        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/bin/bash")
        process.arguments = ["-lc", detachedCommand]
        process.currentDirectoryURL = URL(fileURLWithPath: appSupportDir, isDirectory: true)
        process.standardInput = FileHandle.nullDevice
        let outputPipe = Pipe()
        process.standardOutput = outputPipe
        process.standardError = outputPipe

        do {
            try process.run()
            process.waitUntilExit()
        } catch {
            return nil
        }

        guard process.terminationStatus == 0 else {
            if
                let outputData = try? outputPipe.fileHandleForReading.readToEnd(),
                let output = String(data: outputData, encoding: .utf8),
                !output.isEmpty
            {
                try? output.data(using: .utf8)?.write(
                    to: URL(fileURLWithPath: logPath),
                    options: .atomic
                )
            }
            return nil
        }

        let deadline = Date().addingTimeInterval(10)
        while Date() < deadline {
            if let pid = self.pidFromFile(pidFileURL) {
                return pid
            }
            usleep(200_000)
        }
        return nil
    }

    private nonisolated static func helperStackScriptPath(appSupportDir: String) -> String {
        "\(appSupportDir)/helper-scripts/viventium-stack.sh"
    }

    private nonisolated static func helperDetachedCommandScriptPath(
        appSupportDir: String,
        pidFileName: String
    ) -> String {
        "\(appSupportDir)/helper-scripts/\(pidFileName).sh"
    }

    private nonisolated static func legacyHelperDetachedCommandScriptPath(
        appSupportDir: String,
        pidFileName: String
    ) -> String {
        "\(appSupportDir)/helper-scripts/\(pidFileName).command"
    }

    private nonisolated static func shellQuoted(_ value: String) -> String {
        "'" + value.replacingOccurrences(of: "'", with: "'\"'\"'") + "'"
    }

    private nonisolated static func appleScriptQuoted(_ value: String) -> String {
        "\"" + value
            .replacingOccurrences(of: "\\", with: "\\\\")
            .replacingOccurrences(of: "\"", with: "\\\"")
            .replacingOccurrences(of: "\n", with: "\\n")
            + "\""
    }

    private nonisolated static func pidFromFile(_ url: URL) -> Int32? {
        guard
            let data = try? Data(contentsOf: url),
            let value = String(data: data, encoding: .utf8)?
                .trimmingCharacters(in: .whitespacesAndNewlines),
            let pid = Int32(value)
        else {
            return nil
        }
        try? FileManager.default.removeItem(at: url)
        return pid
    }

    @discardableResult
    private nonisolated static func runCLI(
        repoRoot: String,
        appSupportDir: String,
        arguments: [String],
        logFileName: String? = nil,
        environmentOverrides: [String: String] = [:]
    ) -> Int32 {
        let process = self.makeCLIProcess(
            repoRoot: repoRoot,
            appSupportDir: appSupportDir,
            arguments: arguments,
            logFileName: logFileName,
            environmentOverrides: environmentOverrides
        )
        do {
            try process.run()
            process.waitUntilExit()
            return process.terminationStatus
        } catch {
            return -1
        }
    }

    private func openBrowser() {
        guard let url = URL(string: self.openURLString) else { return }
        NSWorkspace.shared.open(url)
    }
}

private struct RuntimePorts {
    let apiPort: Int
    let frontendPort: Int
    let playgroundPort: Int
    let runtimeProfile: String
    let managedStopCheckURLs: [String]
}

private struct RuntimeEnvParser {
    func readRuntime(appSupportDir: String) -> RuntimePorts {
        let runtimeDir = "\(appSupportDir)/runtime"
        var values = self.parseFile("\(runtimeDir)/runtime.env")
        let localValues = self.parseFile("\(runtimeDir)/runtime.local.env")
        for (key, value) in localValues {
            values[key] = value
        }
        let apiPort = Int(values["VIVENTIUM_LC_API_PORT"] ?? "") ?? 3180
        let frontendPort = Int(values["VIVENTIUM_LC_FRONTEND_PORT"] ?? "") ?? 3190
        let playgroundPort = Int(values["VIVENTIUM_PLAYGROUND_PORT"] ?? "") ?? 3300
        let runtimeProfile = values["VIVENTIUM_RUNTIME_PROFILE"] ?? "isolated"
        return RuntimePorts(
            apiPort: apiPort,
            frontendPort: frontendPort,
            playgroundPort: playgroundPort,
            runtimeProfile: runtimeProfile,
            managedStopCheckURLs: self.managedStopCheckURLs(values: values)
        )
    }

    private func parseFile(_ path: String) -> [String: String] {
        guard let contents = try? String(contentsOfFile: path, encoding: .utf8) else {
            return [:]
        }
        var result: [String: String] = [:]
        for rawLine in contents.split(separator: "\n", omittingEmptySubsequences: false) {
            let line = rawLine.trimmingCharacters(in: .whitespacesAndNewlines)
            if line.isEmpty || line.hasPrefix("#") {
                continue
            }
            guard let separator = line.firstIndex(of: "=") else {
                continue
            }
            let key = String(line[..<separator]).trimmingCharacters(in: .whitespaces)
            var value = String(line[line.index(after: separator)...]).trimmingCharacters(in: .whitespaces)
            if value.hasPrefix("\""), value.hasSuffix("\""), value.count >= 2 {
                value.removeFirst()
                value.removeLast()
            }
            result[key] = value
        }
        return result
    }

    private func managedStopCheckURLs(values: [String: String]) -> [String] {
        var urls: [String] = []
        if self.boolValue(values["START_SCHEDULING_MCP"]) {
            self.appendURL(self.rebasedURL(values["SCHEDULING_MCP_URL"], path: "/health"), to: &urls)
        }
        if self.boolValue(values["START_GOOGLE_MCP"]) {
            self.appendURL(self.rebasedURL(values["GOOGLE_WORKSPACE_MCP_URL"], path: "/health"), to: &urls)
        }
        if self.boolValue(values["START_MS365_MCP"]) {
            self.appendURL(self.rebasedURL(values["MS365_MCP_SERVER_URL"], path: "/mcp"), to: &urls)
        }
        if self.boolValue(values["START_RAG_API"]) {
            let ragPort = Int(values["VIVENTIUM_RAG_API_PORT"] ?? "") ?? 8110
            self.appendURL("http://127.0.0.1:\(ragPort)/health", to: &urls)
        }
        if self.boolValue(values["START_FIRECRAWL"]) {
            self.appendURL(self.trimmedURL(values["FIRECRAWL_API_URL"] ?? values["FIRECRAWL_BASE_URL"]), to: &urls)
        }
        if self.boolValue(values["START_SEARXNG"]) {
            self.appendURL(self.trimmedURL(values["SEARXNG_INSTANCE_URL"] ?? values["SEARXNG_BASE_URL"]), to: &urls)
        }
        if self.boolValue(values["VIVENTIUM_VOICE_ENABLED"] ?? "true") {
            let livekitFallbackPort = Int(values["LIVEKIT_HTTP_PORT"] ?? "") ?? 7888
            self.appendURL(
                self.trimmedURL(values["LIVEKIT_API_HOST"]) ?? "http://127.0.0.1:\(livekitFallbackPort)",
                to: &urls
            )
        }
        return urls
    }

    private func boolValue(_ raw: String?) -> Bool {
        guard let normalized = raw?.trimmingCharacters(in: .whitespacesAndNewlines).lowercased() else {
            return false
        }
        return normalized == "1" || normalized == "true" || normalized == "yes" || normalized == "on"
    }

    private func appendURL(_ raw: String?, to urls: inout [String]) {
        guard let trimmed = self.trimmedURL(raw), !urls.contains(trimmed) else {
            return
        }
        urls.append(trimmed)
    }

    private func trimmedURL(_ raw: String?) -> String? {
        guard let raw = raw?.trimmingCharacters(in: .whitespacesAndNewlines), !raw.isEmpty else {
            return nil
        }
        return raw
    }

    private func rebasedURL(_ raw: String?, path: String) -> String? {
        guard let raw = self.trimmedURL(raw),
              var components = URLComponents(string: raw)
        else {
            return nil
        }
        components.path = path
        components.query = nil
        components.fragment = nil
        return components.string
    }
}

private extension HelperController {
    nonisolated static func stopCompletionReached(runtime: RuntimePorts, appSupportDir: String) async -> Bool {
        if await self.userFacingSurfaceHealthy(runtime: runtime) {
            return false
        }
        if await self.managedServicesRunning(runtime: runtime) {
            return false
        }
        return !self.telegramBridgeRunning(runtime: runtime, appSupportDir: appSupportDir)
    }

    nonisolated static func managedServicesRunning(runtime: RuntimePorts) async -> Bool {
        for urlString in runtime.managedStopCheckURLs {
            if await self.endpointResponding(urlString: urlString) {
                return true
            }
        }
        return false
    }

    nonisolated static func managedServicesHealthy(runtime: RuntimePorts) async -> Bool {
        for urlString in runtime.managedStopCheckURLs {
            if !(await self.endpointResponding(urlString: urlString)) {
                return false
            }
        }
        return true
    }

    nonisolated static func endpointResponding(urlString: String) async -> Bool {
        guard let url = URL(string: urlString) else {
            return false
        }

        return await self.firstHTTPStatus(urls: self.candidateURLs(for: url)) != nil
    }

    nonisolated static func stackOwnedByDifferentRepo(
        runtime: RuntimePorts,
        appSupportDir: String,
        expectedRepoRoot: String
    ) async -> Bool {
        guard
            let ownerState = self.loadStackOwnerState(appSupportDir: appSupportDir, runtimeProfile: runtime.runtimeProfile)
        else {
            return false
        }

        let expected = URL(fileURLWithPath: expectedRepoRoot).standardizedFileURL.path
        let actual = URL(fileURLWithPath: ownerState.repoRoot).standardizedFileURL.path
        guard expected != actual else {
            return false
        }

        if await self.userFacingSurfaceHealthy(runtime: runtime) {
            return true
        }
        return await self.managedServicesRunning(runtime: runtime)
    }

    nonisolated static func loadStackOwnerState(appSupportDir: String, runtimeProfile: String) -> StackOwnerState? {
        let ownerURL = URL(fileURLWithPath: appSupportDir, isDirectory: true)
            .appendingPathComponent("state/runtime/\(runtimeProfile)/stack-owner.json")
        guard
            let data = try? Data(contentsOf: ownerURL),
            let decoded = try? JSONDecoder().decode(StackOwnerState.self, from: data)
        else {
            return nil
        }
        return decoded
    }

    nonisolated static func telegramBridgeRunning(runtime: RuntimePorts, appSupportDir: String) -> Bool {
        let runtimeRoot = URL(fileURLWithPath: appSupportDir, isDirectory: true)
            .appendingPathComponent("state/runtime/\(runtime.runtimeProfile)", isDirectory: true)
        let legacyLogRoot = runtimeRoot.appendingPathComponent("logs", isDirectory: true)
        let pidFiles = [
            runtimeRoot.appendingPathComponent("telegram_bot.pid"),
            runtimeRoot.appendingPathComponent("telegram_codex.pid"),
            legacyLogRoot.appendingPathComponent("telegram_bot.pid"),
            legacyLogRoot.appendingPathComponent("telegram_codex.pid"),
        ]
        return pidFiles.contains { self.pidFileProcessRunning($0) }
    }

    nonisolated static func pidFileProcessRunning(_ url: URL) -> Bool {
        guard
            let raw = try? String(contentsOf: url, encoding: .utf8).trimmingCharacters(in: .whitespacesAndNewlines),
            let pid = Int32(raw),
            pid > 0
        else {
            return false
        }
        return Darwin.kill(pid, 0) == 0 || errno == EPERM
    }
}
private enum LocalNetworkAddressResolver {
    static func currentHost() -> String? {
        var pointer: UnsafeMutablePointer<ifaddrs>?
        guard getifaddrs(&pointer) == 0, let first = pointer else {
            return nil
        }
        defer { freeifaddrs(pointer) }

        if let prioritized = address(from: first, interfacePrefixes: ["en0", "en1"]) {
            return prioritized
        }
        return address(from: first, interfacePrefixes: nil)
    }

    private static func address(
        from first: UnsafeMutablePointer<ifaddrs>,
        interfacePrefixes: [String]?
    ) -> String? {
        var current = first
        while true {
            let interface = current.pointee
            let flags = Int32(interface.ifa_flags)
            let isUp = (flags & IFF_UP) != 0
            let isLoopback = (flags & IFF_LOOPBACK) != 0
            if isUp,
               !isLoopback,
               let addr = interface.ifa_addr,
               addr.pointee.sa_family == UInt8(AF_INET),
               let name = String(validatingCString: interface.ifa_name),
               !name.hasPrefix("utun")
            {
                let matchesPreferred = interfacePrefixes == nil || interfacePrefixes?.contains(where: { name.hasPrefix($0) }) == true
                if matchesPreferred {
                    var host = [CChar](repeating: 0, count: Int(NI_MAXHOST))
                    let result = getnameinfo(
                        addr,
                        socklen_t(addr.pointee.sa_len),
                        &host,
                        socklen_t(host.count),
                        nil,
                        0,
                        NI_NUMERICHOST)
                    if result == 0 {
                        let candidate = String(decoding: host.prefix { $0 != 0 }.map(UInt8.init), as: UTF8.self)
                        if !candidate.hasPrefix("169.254.") {
                            return candidate
                        }
                    }
                }
            }
            guard let next = interface.ifa_next else {
                break
            }
            current = next
        }
        return nil
    }
}

@main
struct ViventiumHelperApp: App {
    @StateObject private var controller = HelperController()

    var body: some Scene {
        MenuBarExtra(
            isInserted: Binding(
                get: { self.controller.showInStatusBarEnabled },
                set: { self.controller.setShowInStatusBar($0) }
            )
        ) {
            Button("Open") {
                self.controller.openViventium()
            }
            Button(self.controller.actionLabel) {
                self.controller.toggleStack()
            }
            .disabled(self.controller.actionDisabled)
            if self.controller.showsStatusRow {
                Divider()
                Button(self.controller.statusLabel) {}
                    .disabled(true)
            }
            Toggle(
                "Start at Login",
                isOn: Binding(
                    get: { self.controller.launchAtLoginEnabled },
                    set: { self.controller.setLaunchAtLogin($0) }
                )
            )
            Toggle(
                "Show in Status Bar",
                isOn: Binding(
                    get: { self.controller.showInStatusBarEnabled },
                    set: { self.controller.setShowInStatusBar($0) }
                )
            )
            Divider()
            Button("Quit") {
                self.controller.quit()
            }
            .disabled(self.controller.actionDisabled)
        } label: {
            Text("V")
                .font(.system(size: 13, weight: .bold, design: .rounded))
        }

        Settings {
            EmptyView()
        }
    }
}

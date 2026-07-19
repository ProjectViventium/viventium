import AppKit
import Darwin
import Foundation
import SwiftUI

private struct HelperConfig: Codable, Equatable {
    let repoRoot: String
    let appSupportDir: String
    var allowProtectedRepoRoot: Bool?
    var showInStatusBar: Bool?
}

private struct ActiveRuntimeCheckout: Decodable {
    let repoRoot: String
    let allowProtectedFolderAccess: Bool?
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

private struct CommandCaptureResult {
    let exitStatus: Int32
    let stdout: String
}

private struct StackHealthSnapshot {
    let apiReady: Bool
    let frontendReady: Bool
    let playgroundReady: Bool
    let optionalSurfacesReady: Bool

    var coreHealthy: Bool {
        self.apiReady && self.frontendReady && self.playgroundReady
    }

    var healthy: Bool {
        self.coreHealthy && self.optionalSurfacesReady
    }

    var needsAttention: Bool {
        self.coreHealthy && !self.optionalSurfacesReady
    }

    var preferredSurfaceIsPlaygroundOnly: Bool {
        !self.coreHealthy && self.playgroundReady
    }
}

private struct HealWorkflowSettings {
    let provider: String
    let reasoningEffort: String
}

private struct BugReportInput {
    let whatHappened: String
    let stepsToReproduce: String
    let expected: String
    let actual: String
    let details: String
}

private enum TranscriptIngestSourceStatus: Equatable {
    case ready
    case notConfigured
    case unavailable
}

enum StackState: Equatable {
    case running
    case needsAttention
    case stopped
    case starting
    case stopping
    case unavailable(String)

    var menuLabel: String {
        switch self {
        case .running:
            return "Running"
        case .needsAttention:
            return "Needs Attention"
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
        case .needsAttention:
            return "Repair"
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
    @Published private(set) var snapshotInProgress: Bool = false
    @Published private(set) var transcriptIngestInProgress: Bool = false
    @Published private(set) var transcriptSourceConfigInProgress: Bool = false
    @Published private(set) var promptWorkbenchActionInProgress: Bool = false
    @Published private(set) var workflowStatusLabel: String?
    @Published private(set) var workflowActionInProgress: Bool = false
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
    private static let transcriptPartialExitStatus: Int32 = 2
    // Heavy local stacks can legitimately take several minutes to drain all owned sidecars
    // after the initial bounded stop command has returned.
    private let delayedQuitWatchTimeoutSeconds: Int = 420
    private var didAttemptLaunchAutostart = false
    private var delayedQuitWatchTask: Task<Void, Never>?
    private var busyStateGraceDeadline: Date?
    private var activatedHelperLifecycle = false
    private var launchAtLoginRefreshTask: Task<Void, Never>?
    private var steadyStateHealthSnapshot: (runtime: RuntimePorts, checkedAt: Date, snapshot: StackHealthSnapshot)?
    private let steadyStateHealthRefreshInterval: TimeInterval = 30
    private let automaticTerminationReason = "Viventium status-bar helper keeps the local runtime available after login."

    init() {
        ProcessInfo.processInfo.disableAutomaticTermination(self.automaticTerminationReason)
        self.config = Self.loadConfig()
        self.helperLogURL = Self.makeHelperLogURL(appSupportDir: self.config?.appSupportDir)
        self.launchAtLoginEnabled = Self.launchAtLoginFastPathEnabled()
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
        if let workflowStatusLabel {
            return workflowStatusLabel
        }
        return self.stackState.menuLabel
    }

    var menuGlyph: String {
        self.workflowStatusLabel == nil ? "V" : "V*"
    }

    var actionDisabled: Bool {
        self.stackState.actionBusy || self.config == nil || self.configUsesProtectedRepoRoot
    }

    var backupActionLabel: String {
        self.snapshotInProgress ? "Creating Backup..." : "Create Backup Snapshot"
    }

    var backupActionDisabled: Bool {
        self.snapshotInProgress || self.stackState.actionBusy || self.config == nil || self.configUsesProtectedRepoRoot
    }

    var transcriptIngestActionLabel: String {
        self.transcriptIngestInProgress ? "Ingesting Transcripts..." : "Ingest Meeting Transcripts"
    }

    var transcriptIngestActionDisabled: Bool {
        self.transcriptIngestInProgress || self.stackState.actionBusy || self.config == nil || self.configUsesProtectedRepoRoot
    }

    var transcriptSourceActionLabel: String {
        self.transcriptSourceConfigInProgress ? "Choosing Transcripts Folder..." : "Choose Transcripts Folder..."
    }

    var transcriptSourceActionDisabled: Bool {
        self.transcriptSourceConfigInProgress || self.stackState.actionBusy || self.config == nil || self.configUsesProtectedRepoRoot
    }

    var promptWorkbenchActionDisabled: Bool {
        self.promptWorkbenchActionInProgress || self.config == nil || self.configUsesProtectedRepoRoot
    }

    var promptWorkbenchMenuTitle: String {
        self.promptWorkbenchActionInProgress ? "Prompt Workbench (Working...)" : "Prompt Workbench"
    }

    var workflowActionDisabled: Bool {
        self.workflowActionInProgress || self.config == nil || self.configUsesProtectedRepoRoot
    }

    var showsStatusRow: Bool {
        !self.stackState.actionBusy
    }

    private var configUsesProtectedRepoRoot: Bool {
        guard let config else {
            return false
        }
        return Self.configUsesProtectedRepoRoot(config)
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
        case .running, .needsAttention:
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

    func openFeelings() {
        switch self.stackState {
        case .running, .needsAttention:
            self.openBrowser(path: "/feelings")
        case .starting, .stopping:
            return
        case .stopped, .unavailable:
            let alert = NSAlert()
            alert.messageText = "Viventium is not running"
            alert.informativeText = "Start Viventium now and open Feelings in your browser?"
            alert.alertStyle = .informational
            alert.addButton(withTitle: "Start and Open Feelings")
            alert.addButton(withTitle: "Cancel")
            let response = alert.runModal()
            if response == .alertFirstButtonReturn {
                self.startStack(openWhenReady: true, openPath: "/feelings")
            }
        }
    }

    func toggleStack() {
        switch self.stackState {
        case .running:
            self.stopStack()
        case .needsAttention, .stopped, .unavailable:
            self.startStack(openWhenReady: false)
        case .starting, .stopping:
            return
        }
    }

    func createBackupSnapshot() {
        guard let config else {
            let alert = NSAlert()
            alert.messageText = "Missing helper config"
            alert.informativeText = "Reinstall the Viventium helper from this checkout, then try again."
            alert.alertStyle = .warning
            alert.addButton(withTitle: "OK")
            alert.runModal()
            return
        }
        guard !Self.configUsesProtectedRepoRoot(config) else {
            self.presentProtectedCheckoutAlert(action: "create a backup")
            return
        }
        guard !self.snapshotInProgress else {
            return
        }

        self.snapshotInProgress = true
        self.log("Manual backup snapshot requested")

        Task.detached(priority: .userInitiated) {
            let exitStatus = Self.runCLI(
                repoRoot: config.repoRoot,
                appSupportDir: config.appSupportDir,
                arguments: ["snapshot"],
                logFileName: "helper-snapshot.log"
            )
            let snapshotPath = Self.latestSnapshotPath(appSupportDir: config.appSupportDir)
            await MainActor.run {
                self.snapshotInProgress = false
                if exitStatus == 0 {
                    self.log("Manual backup snapshot completed")
                    let alert = NSAlert()
                    alert.messageText = "Backup snapshot created"
                    alert.informativeText =
                        snapshotPath.map { "Saved to \($0)" } ??
                        "The snapshot completed, but the latest snapshot path was not recorded."
                    alert.alertStyle = .informational
                    if snapshotPath != nil {
                        alert.addButton(withTitle: "Reveal")
                    }
                    alert.addButton(withTitle: "OK")
                    let response = alert.runModal()
                    if response == .alertFirstButtonReturn, let snapshotPath {
                        NSWorkspace.shared.activateFileViewerSelecting([URL(fileURLWithPath: snapshotPath)])
                    }
                } else {
                    self.log("Manual backup snapshot failed with status \(exitStatus)")
                    let alert = NSAlert()
                    alert.messageText = "Backup snapshot failed"
                    alert.informativeText = "Check helper-snapshot.log and try again."
                    alert.alertStyle = .warning
                    alert.addButton(withTitle: "OK")
                    alert.runModal()
                }
            }
        }
    }

    func ingestMeetingTranscripts() {
        guard let config else {
            let alert = NSAlert()
            alert.messageText = "Missing helper config"
            alert.informativeText = "Reinstall the Viventium helper from this checkout, then try again."
            alert.alertStyle = .warning
            alert.addButton(withTitle: "OK")
            alert.runModal()
            return
        }
        guard !Self.configUsesProtectedRepoRoot(config) else {
            self.presentProtectedCheckoutAlert(action: "ingest meeting transcripts")
            return
        }
        guard !self.transcriptIngestInProgress else {
            return
        }

        switch Self.transcriptIngestSourceStatus(config: config) {
        case .ready:
            break
        case .notConfigured:
            self.log("Transcript ingest blocked; no configured transcript source")
            self.presentTranscriptIngestAlert(
                title: "No transcript source is configured",
                message: "Configure runtime.memory_hardening.transcripts.source_dir, then refresh Viventium before ingesting transcripts."
            )
            return
        case .unavailable:
            self.log("Transcript ingest blocked; configured transcript source is unavailable")
            self.presentTranscriptIngestAlert(
                title: "Transcript source is unavailable",
                message: "The configured transcript source folder could not be read as a folder. Check the Viventium config and try again."
            )
            return
        }

        let ingestScope = Self.transcriptIngestScopeDescription(config: config)
        let confirm = NSAlert()
        confirm.messageText = "Ingest meeting transcripts?"
        confirm.informativeText = "Viventium will process the configured transcript source for \(ingestScope)."
        confirm.alertStyle = .informational
        confirm.addButton(withTitle: "Ingest")
        confirm.addButton(withTitle: "Cancel")
        guard confirm.runModal() == .alertFirstButtonReturn else {
            self.log("Manual transcript ingest cancelled; scope: \(ingestScope)")
            return
        }

        self.transcriptIngestInProgress = true
        self.log("Manual transcript ingest requested; scope: \(ingestScope)")
        Self.appendHelperLog(
            Self.makeNamedHelperLogURL(appSupportDir: config.appSupportDir, logFileName: "helper-transcript-ingest.log"),
            "Manual transcript ingest requested; scope: \(ingestScope)"
        )

        Task.detached(priority: .userInitiated) {
            let runResult = Self.runMemoryHardeningCaptured(
                repoRoot: config.repoRoot,
                appSupportDir: config.appSupportDir,
                arguments: [
                    "ingest-transcripts",
                    "--apply",
                    "--until-caught-up",
                    "--max-batches",
                    "1",
                    "--transcript-max-files-per-run",
                    "5",
                    "--interactive-maintenance",
                    "--ignore-idle-gate",
                    "--skip-model-probe",
                    "--json"
                ]
            )
            let exitStatus = runResult.exitStatus
            let runSummary = Self.transcriptIngestRunSummary(stdout: runResult.stdout)
            await MainActor.run {
                self.transcriptIngestInProgress = false
                let logSummary = runSummary.map { "; \($0.message)" } ?? ""
                let incomplete = exitStatus == Self.transcriptPartialExitStatus || runSummary?.incomplete == true
                let statusMessage: String
                if exitStatus == 0 {
                    statusMessage = runSummary?.skipped == true
                        ? "Manual transcript ingest skipped; scope: \(ingestScope)\(logSummary)"
                        : "Manual transcript ingest completed; scope: \(ingestScope)\(logSummary)"
                } else if incomplete {
                    statusMessage = "Manual transcript ingest incomplete with status \(exitStatus); scope: \(ingestScope)\(logSummary)"
                } else {
                    statusMessage = "Manual transcript ingest failed with status \(exitStatus); scope: \(ingestScope)\(logSummary)"
                }
                self.log(statusMessage)
                Self.appendHelperLog(
                    Self.makeNamedHelperLogURL(
                        appSupportDir: config.appSupportDir,
                        logFileName: "helper-transcript-ingest.log"
                    ),
                    statusMessage
                )
                let alert = NSAlert()
                if exitStatus == 0 {
                    alert.messageText = runSummary?.skipped == true ? "Transcript ingest skipped" : "Transcript ingest completed"
                    alert.informativeText = [
                        runSummary?.skipped == true
                            ? "Viventium did not scan the configured transcript source for \(ingestScope)."
                            : "Viventium processed the configured transcript source for \(ingestScope).",
                        runSummary?.message,
                    ].compactMap { $0 }.joined(separator: "\n\n")
                    alert.alertStyle = .informational
                } else if incomplete {
                    alert.messageText = "Transcript ingest incomplete"
                    alert.informativeText = [
                        "Viventium processed a bounded transcript batch for \(ingestScope), but catch-up is not fully complete.",
                        runSummary?.message,
                        "Run ingest again to continue, or let the 3am memory job continue it.",
                    ].compactMap { $0 }.joined(separator: "\n\n")
                    alert.alertStyle = .informational
                    alert.addButton(withTitle: "Run Again")
                } else {
                    alert.messageText = "Transcript ingest failed"
                    alert.informativeText = "The ingest was scoped to \(ingestScope). Check helper-transcript-ingest.log for status, then run the same CLI command from Terminal if detailed diagnostics are needed."
                    alert.alertStyle = .warning
                }
                alert.addButton(withTitle: "OK")
                if alert.runModal() == .alertFirstButtonReturn, incomplete {
                    self.ingestMeetingTranscripts()
                }
            }
        }
    }

    func chooseTranscriptsFolder() {
        guard let config else {
            self.presentMissingConfigAlert()
            return
        }
        guard !Self.configUsesProtectedRepoRoot(config) else {
            self.presentProtectedCheckoutAlert(action: "choose a transcripts folder")
            return
        }
        guard !self.transcriptSourceConfigInProgress else {
            return
        }

        let panel = NSOpenPanel()
        panel.title = "Choose Transcripts Folder"
        panel.message = "Choose the local folder where Viventium should read meeting transcripts."
        panel.prompt = "Choose"
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = false
        panel.canCreateDirectories = true

        guard panel.runModal() == .OK, let selectedURL = panel.url else {
            self.log("Choose transcripts folder cancelled")
            return
        }

        let selectedPath = selectedURL.path
        self.transcriptSourceConfigInProgress = true
        self.log("Choose transcripts folder requested")
        Self.appendHelperLog(
            Self.makeNamedHelperLogURL(appSupportDir: config.appSupportDir, logFileName: "helper-transcript-source.log"),
            "Choose transcripts folder requested"
        )

        Task.detached(priority: .userInitiated) {
            let result = Self.runCLICaptured(
                repoRoot: config.repoRoot,
                appSupportDir: config.appSupportDir,
                arguments: ["transcripts", "source", "set", selectedPath, "--json"],
                logFileName: "helper-transcript-source.log",
                timeoutSeconds: 120
            )
            await MainActor.run {
                self.transcriptSourceConfigInProgress = false
                let statusMessage = result.exitStatus == 0
                    ? "Transcript source folder saved"
                    : "Transcript source folder save failed with status \(result.exitStatus)"
                self.log(statusMessage)
                Self.appendHelperLog(
                    Self.makeNamedHelperLogURL(appSupportDir: config.appSupportDir, logFileName: "helper-transcript-source.log"),
                    statusMessage
                )

                let alert = NSAlert()
                if result.exitStatus == 0 {
                    alert.messageText = "Transcript folder saved"
                    alert.informativeText = "Viventium will use the selected folder for meeting transcript memory. Use Ingest Meeting Transcripts to process new files; if you changed an existing folder while Viventium is running, restart before relying on chat recall."
                    alert.alertStyle = .informational
                    alert.addButton(withTitle: "Ingest Now")
                    alert.addButton(withTitle: "OK")
                    if alert.runModal() == .alertFirstButtonReturn {
                        self.ingestMeetingTranscripts()
                    }
                } else {
                    alert.messageText = "Could not save transcript folder"
                    alert.informativeText = "Check helper-transcript-source.log, then try again."
                    alert.alertStyle = .warning
                    alert.addButton(withTitle: "OK")
                    alert.runModal()
                }
            }
        }
    }

    func checkForUpdates() {
        guard let config else {
            self.presentMissingConfigAlert()
            return
        }
        guard !Self.configUsesProtectedRepoRoot(config) else {
            self.presentProtectedCheckoutAlert(action: "check for updates")
            return
        }
        self.workflowActionInProgress = true
        Task.detached(priority: .userInitiated) {
            let result = Self.runCLICaptured(
                repoRoot: config.repoRoot,
                appSupportDir: config.appSupportDir,
                arguments: ["upgrade", "--check", "--json"],
                logFileName: "helper-update-check.log",
                timeoutSeconds: 30
            )
            let summary = Self.updateCheckSummary(stdout: result.stdout)
            await MainActor.run {
                self.workflowActionInProgress = false
                let alert = NSAlert()
                if result.exitStatus != 0 {
                    alert.messageText = "Could not check for updates"
                    alert.informativeText = "Viventium could not complete the update check. Check helper-update-check.log, then try again."
                    alert.alertStyle = .warning
                    alert.addButton(withTitle: "OK")
                    alert.runModal()
                    return
                }
                alert.messageText = summary.title
                alert.informativeText = summary.message
                alert.alertStyle = summary.blockers.isEmpty ? .informational : .warning
                if summary.updateAvailable && summary.blockers.isEmpty {
                    alert.addButton(withTitle: "Install Update")
                    alert.addButton(withTitle: "Cancel")
                    if alert.runModal() == .alertFirstButtonReturn {
                        self.installUpdate(config: config)
                    }
                } else {
                    alert.addButton(withTitle: "OK")
                    alert.runModal()
                }
            }
        }
    }

    func startHealWorkflow() {
        guard let settings = self.promptForHealSettings() else {
            return
        }
        self.startWorkflow(
            title: "Start Viventium Heal?",
            message: "Viventium will use the local GlassHive host-worker workflow with the selected provider and reasoning effort.",
            arguments: [
                "heal",
                "start",
                "--provider",
                settings.provider,
                "--reasoning-effort",
                settings.reasoningEffort,
            ],
            logFileName: "helper-heal.log"
        )
    }

    func startFeatureRequestWorkflow() {
        guard let request = self.promptForFeatureRequest(), !request.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            return
        }
        self.startWorkflow(
            title: "Start Feature Request?",
            message: "Viventium will collect success criteria and non-obvious cases before any implementation work begins.",
            arguments: ["feature-request", "start", "--request", request],
            logFileName: "helper-feature-request.log"
        )
    }

    func startBugReportWorkflow() {
        guard let report = self.promptForBugReport(), !report.whatHappened.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            return
        }
        self.startWorkflow(
            title: "Start Bug Report?",
            message: "Viventium will collect reproduction details, expected behavior, actual behavior, and QA acceptance before any fix work begins.",
            arguments: [
                "report-bug",
                "start",
                "--what-happened",
                report.whatHappened,
                "--steps-to-reproduce",
                report.stepsToReproduce,
                "--expected",
                report.expected,
                "--actual",
                report.actual,
                "--details",
                report.details,
            ],
            logFileName: "helper-bug-report.log"
        )
    }

    func openWorkflowArtifacts() {
        guard let config else {
            self.presentMissingConfigAlert()
            return
        }
        _ = Self.runCLI(
            repoRoot: config.repoRoot,
            appSupportDir: config.appSupportDir,
            arguments: ["workflows", "open-artifacts"],
            logFileName: "helper-workflows.log"
        )
    }

    func openPromptWorkbench() {
        self.runPromptWorkbenchAction(
            action: "open",
            successTitle: nil,
            successFallbackMessage: "Prompt Workbench opened in your browser."
        )
    }

    func startPromptWorkbench() {
        self.runPromptWorkbenchAction(
            action: "start",
            successTitle: "Prompt Workbench started",
            successFallbackMessage: "The local Prompt Workbench web app is running."
        )
    }

    func stopPromptWorkbench() {
        self.runPromptWorkbenchAction(
            action: "stop",
            successTitle: "Prompt Workbench stopped",
            successFallbackMessage: "Only the Prompt Workbench web app was stopped. Viventium keeps its current running state."
        )
    }

    func approveFeatureWorkflow() {
        self.runWorkflowControlAction(
            title: "Approve Build or Fix?",
            message: "Viventium will create an isolated local worktree and ask GlassHive to implement only from the approved feature or bug report.",
            arguments: ["workflows", "approve"],
            logFileName: "helper-workflows.log"
        )
    }

    func cancelWorkflow() {
        self.runWorkflowControlAction(
            title: "Cancel Active Workflow?",
            message: "Viventium will mark the local workflow as cancelled and remove it from the active status view.",
            arguments: ["workflows", "cancel"],
            logFileName: "helper-workflows.log"
        )
    }

    private func runPromptWorkbenchAction(action: String, successTitle: String?, successFallbackMessage: String) {
        guard let config else {
            self.presentMissingConfigAlert()
            return
        }
        guard !Self.configUsesProtectedRepoRoot(config) else {
            self.presentProtectedCheckoutAlert(action: "\(action) Prompt Workbench")
            return
        }
        guard !self.promptWorkbenchActionInProgress else {
            return
        }
        self.promptWorkbenchActionInProgress = true
        self.log("Prompt Workbench \(action) requested")
        Task.detached(priority: .userInitiated) {
            let result = Self.runCLICaptured(
                repoRoot: config.repoRoot,
                appSupportDir: config.appSupportDir,
                arguments: ["prompt-workbench", action, "--json"],
                logFileName: "helper-prompt-workbench.log"
            )
            let resultURL = Self.parseJSONObject(result.stdout)?["url"] as? String
            await MainActor.run {
                self.promptWorkbenchActionInProgress = false
                if result.exitStatus == 0 {
                    self.log("Prompt Workbench \(action) completed")
                    guard let successTitle else {
                        return
                    }
                    let message = resultURL.map { "\($0)\n\n\(successFallbackMessage)" } ?? successFallbackMessage
                    let alert = NSAlert()
                    alert.messageText = successTitle
                    alert.informativeText = message
                    alert.alertStyle = .informational
                    alert.addButton(withTitle: "OK")
                    alert.runModal()
                    return
                }

                self.log("Prompt Workbench \(action) failed with status \(result.exitStatus)")
                let alert = NSAlert()
                alert.messageText = "Prompt Workbench action failed"
                alert.informativeText = "Check helper-prompt-workbench.log, then try again."
                alert.alertStyle = .warning
                alert.addButton(withTitle: "OK")
                alert.runModal()
            }
        }
    }

    private func runWorkflowControlAction(title: String, message: String, arguments: [String], logFileName: String) {
        guard let config else {
            self.presentMissingConfigAlert()
            return
        }
        guard !self.workflowActionInProgress else {
            return
        }
        let confirm = NSAlert()
        confirm.messageText = title
        confirm.informativeText = message
        confirm.alertStyle = .informational
        confirm.addButton(withTitle: "Continue")
        confirm.addButton(withTitle: "Cancel")
        guard confirm.runModal() == .alertFirstButtonReturn else {
            return
        }
        self.workflowActionInProgress = true
        Task.detached(priority: .userInitiated) {
            let exitStatus = Self.runCLI(
                repoRoot: config.repoRoot,
                appSupportDir: config.appSupportDir,
                arguments: arguments,
                logFileName: logFileName
            )
            await MainActor.run {
                self.workflowActionInProgress = false
                self.refreshWorkflowStatus(config: config)
                if exitStatus != 0 {
                    let alert = NSAlert()
                    alert.messageText = "Workflow action failed"
                    alert.informativeText = "Check \(logFileName), then run the same command from Terminal for details."
                    alert.alertStyle = .warning
                    alert.addButton(withTitle: "OK")
                    alert.runModal()
                }
            }
        }
    }

    private func startWorkflow(title: String, message: String, arguments: [String], logFileName: String) {
        guard let config else {
            self.presentMissingConfigAlert()
            return
        }
        guard !Self.configUsesProtectedRepoRoot(config) else {
            self.presentProtectedCheckoutAlert(action: "start this workflow")
            return
        }
        guard !self.workflowActionInProgress else {
            return
        }
        let confirm = NSAlert()
        confirm.messageText = title
        confirm.informativeText = message
        confirm.alertStyle = .informational
        confirm.addButton(withTitle: "Start")
        confirm.addButton(withTitle: "Cancel")
        guard confirm.runModal() == .alertFirstButtonReturn else {
            return
        }
        self.workflowActionInProgress = true
        Task.detached(priority: .userInitiated) {
            let exitStatus = Self.runCLI(
                repoRoot: config.repoRoot,
                appSupportDir: config.appSupportDir,
                arguments: arguments,
                logFileName: logFileName
            )
            await MainActor.run {
                self.workflowActionInProgress = false
                self.refreshWorkflowStatus(config: config)
                let alert = NSAlert()
                if exitStatus == 0 {
                    alert.messageText = "Workflow started"
                    alert.informativeText = "Open Advanced > Open Work Artifacts to inspect the local run files."
                    alert.alertStyle = .informational
                } else {
                    alert.messageText = "Workflow could not start"
                    alert.informativeText = "GlassHive host workers may be disabled or unavailable. Check \(logFileName), then run the same command from Terminal for details."
                    alert.alertStyle = .warning
                }
                alert.addButton(withTitle: "OK")
                alert.runModal()
            }
        }
    }

    private func installUpdate(config: HelperConfig) {
        self.workflowActionInProgress = true
        Task.detached(priority: .userInitiated) {
            let exitStatus = Self.runCLI(
                repoRoot: config.repoRoot,
                appSupportDir: config.appSupportDir,
                arguments: ["upgrade", "--restart"],
                logFileName: "helper-update.log"
            )
            await MainActor.run {
                self.workflowActionInProgress = false
                self.refreshState(force: true)
                let alert = NSAlert()
                alert.messageText = exitStatus == 0 ? "Update installed" : "Update failed"
                alert.informativeText = exitStatus == 0
                    ? "Viventium refreshed and restarted. The helper is rechecking the running surfaces."
                    : "Check helper-update.log and run Heal if the installed runtime is not healthy."
                alert.alertStyle = exitStatus == 0 ? .informational : .warning
                alert.addButton(withTitle: "OK")
                alert.runModal()
            }
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

    private func startStack(openWhenReady: Bool, openPath: String? = nil, launchReason: String = "manual") {
        self.cancelDelayedQuitWatch()
        guard let config else {
            self.log("Start requested without helper config")
            self.stackState = .unavailable("Missing helper config")
            return
        }
        guard !Self.configUsesProtectedRepoRoot(config) else {
            self.presentProtectedCheckoutAlert(action: "start Viventium")
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
                repoRoot: config.repoRoot,
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
                    self.openBrowser(path: openPath)
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
        guard !Self.configUsesProtectedRepoRoot(config) else {
            self.presentProtectedCheckoutAlert(action: "stop Viventium")
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
        if Self.configUsesProtectedRepoRoot(config) {
            self.stackState = .unavailable("Protected Checkout")
            return
        }
        let runtime = self.envParser.readRuntime(appSupportDir: config.appSupportDir)
        let host = LocalNetworkAddressResolver.currentHost() ?? "localhost"
        self.openURLString = Self.frontendURLString(host: host, port: runtime.frontendPort)
        self.refreshLaunchAtLoginState(force: force)
        self.refreshWorkflowStatus(config: config)

        let allowBusyStateTransition = force
        Task {
            let snapshot = await self.stackHealthSnapshot(
                runtime: runtime,
                force: force || self.stackState.actionBusy
            )
            let preferredOpenURLString = Self.preferredOpenURLString(
                runtime: runtime,
                host: host,
                snapshot: snapshot
            )
            let healthy = snapshot.healthy
            let splitWorkspace = await Self.stackOwnedByDifferentRepo(
                runtime: runtime,
                appSupportDir: config.appSupportDir,
                expectedRepoRoot: config.repoRoot,
                knownSnapshot: snapshot
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
            if snapshot.needsAttention {
                self.stackState = .needsAttention
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

    private func stackHealthSnapshot(runtime: RuntimePorts, force: Bool = false) async -> StackHealthSnapshot {
        if !force,
           let cached = self.steadyStateHealthSnapshot,
           cached.runtime == runtime,
           Date().timeIntervalSince(cached.checkedAt) < self.steadyStateHealthRefreshInterval {
            return cached.snapshot
        }

        let snapshot = await Self.stackHealthSnapshot(runtime: runtime, appSupportDir: self.config?.appSupportDir)
        if snapshot.healthy {
            self.steadyStateHealthSnapshot = (runtime, Date(), snapshot)
        } else {
            self.steadyStateHealthSnapshot = nil
        }
        return snapshot
    }

    private func refreshLaunchAtLoginState(force: Bool = false) {
        if !force, self.launchAtLoginRefreshTask != nil {
            return
        }
        self.launchAtLoginRefreshTask?.cancel()
        self.launchAtLoginRefreshTask = Task.detached(priority: .utility) { [weak self] in
            let updated = Self.launchAtLoginIsEnabled()
            guard !Task.isCancelled else {
                return
            }
            await MainActor.run { [weak self] in
                guard let self else {
                    return
                }
                self.launchAtLoginEnabled = updated
                self.launchAtLoginRefreshTask = nil
            }
        }
    }

    private func refreshWorkflowStatus(config: HelperConfig) {
        self.workflowStatusLabel = Self.workflowStatusLabel(appSupportDir: config.appSupportDir)
    }

    private func beginBusyState(_ state: StackState) {
        self.stackState = state
        self.busyStateGraceDeadline = Date().addingTimeInterval(self.busyStateHandoffGraceSeconds)
    }

    private func presentMissingConfigAlert() {
        let alert = NSAlert()
        alert.messageText = "Missing helper config"
        alert.informativeText = "Reinstall the Viventium helper from this checkout, then try again."
        alert.alertStyle = .warning
        alert.addButton(withTitle: "OK")
        alert.runModal()
    }

    private func promptForHealSettings() -> HealWorkflowSettings? {
        let alert = NSAlert()
        alert.messageText = "Heal Settings"
        alert.informativeText = "Choose the local AI worker Viventium should use for this heal run."
        alert.alertStyle = .informational
        alert.addButton(withTitle: "Start")
        alert.addButton(withTitle: "Cancel")

        let providerPopup = NSPopUpButton(frame: .zero, pullsDown: false)
        providerPopup.addItems(withTitles: ["Auto (Codex preferred)", "Codex", "Claude"])
        providerPopup.selectItem(at: 0)

        let effortPopup = NSPopUpButton(frame: .zero, pullsDown: false)
        effortPopup.addItems(withTitles: ["xHigh", "High", "Medium", "Low"])
        effortPopup.selectItem(at: 0)

        let providerRow = NSStackView(views: [
            NSTextField(labelWithString: "Provider"),
            providerPopup,
        ])
        providerRow.orientation = .horizontal
        providerRow.spacing = 12
        providerRow.distribution = .fillEqually

        let effortRow = NSStackView(views: [
            NSTextField(labelWithString: "Thinking"),
            effortPopup,
        ])
        effortRow.orientation = .horizontal
        effortRow.spacing = 12
        effortRow.distribution = .fillEqually

        let stack = NSStackView(views: [providerRow, effortRow])
        stack.orientation = .vertical
        stack.spacing = 10
        stack.frame = NSRect(x: 0, y: 0, width: 420, height: 64)
        alert.accessoryView = stack

        guard alert.runModal() == .alertFirstButtonReturn else {
            return nil
        }

        let provider: String
        switch providerPopup.indexOfSelectedItem {
        case 1:
            provider = "codex"
        case 2:
            provider = "claude"
        default:
            provider = "auto"
        }

        let effort = (effortPopup.titleOfSelectedItem ?? "xHigh").lowercased()
        return HealWorkflowSettings(provider: provider, reasoningEffort: effort)
    }

    private func promptForFeatureRequest() -> String? {
        let alert = NSAlert()
        alert.messageText = "Feature Request"
        alert.informativeText = "Describe the feature. Viventium will collect success criteria and edge cases before implementation."
        alert.alertStyle = .informational
        alert.addButton(withTitle: "Continue")
        alert.addButton(withTitle: "Cancel")
        let input = NSTextField(frame: NSRect(x: 0, y: 0, width: 420, height: 24))
        input.placeholderString = "Example: Add a clearer update progress view"
        alert.accessoryView = input
        guard alert.runModal() == .alertFirstButtonReturn else {
            return nil
        }
        return input.stringValue
    }

    private func promptForBugReport() -> BugReportInput? {
        let alert = NSAlert()
        alert.messageText = "Report a Bug"
        alert.informativeText = "Describe what went wrong. Viventium will collect enough detail to reproduce or validate the bug before any fix starts."
        alert.alertStyle = .informational
        alert.addButton(withTitle: "Continue")
        alert.addButton(withTitle: "Cancel")

        func row(_ label: String, placeholder: String, required: Bool = false) -> (NSStackView, NSTextField) {
            let title = NSTextField(labelWithString: required ? "\(label) *" : label)
            title.toolTip = placeholder
            let input = NSTextField(frame: NSRect(x: 0, y: 0, width: 430, height: 24))
            input.placeholderString = placeholder
            input.toolTip = placeholder
            let stack = NSStackView(views: [title, input])
            stack.orientation = .vertical
            stack.spacing = 4
            return (stack, input)
        }

        let happened = row("What happened?", placeholder: "Example: Update check says healthy, but the app does not restart.", required: true)
        let steps = row("Steps to reproduce", placeholder: "Example: Open helper > Advanced > Check for Updates > Install Update.")
        let expected = row("What should happen?", placeholder: "Example: Viventium installs the update and comes back healthy.")
        let actual = row("What happened instead?", placeholder: "Example: The helper still shows Stopped after the update.")
        let details = row("Other useful details", placeholder: "Example: when it started, affected screen, error text, recent changes.")

        let stack = NSStackView(views: [happened.0, steps.0, expected.0, actual.0, details.0])
        stack.orientation = .vertical
        stack.spacing = 10
        stack.frame = NSRect(x: 0, y: 0, width: 460, height: 260)
        alert.accessoryView = stack

        guard alert.runModal() == .alertFirstButtonReturn else {
            return nil
        }
        return BugReportInput(
            whatHappened: happened.1.stringValue,
            stepsToReproduce: steps.1.stringValue,
            expected: expected.1.stringValue,
            actual: actual.1.stringValue,
            details: details.1.stringValue
        )
    }

    private func presentProtectedCheckoutAlert(action: String) {
        self.log("Blocked \(action); helper is still bound to a protected-folder checkout")
        self.stackState = .unavailable("Protected Checkout")
        let alert = NSAlert()
        alert.messageText = "Viventium helper needs a safe checkout"
        alert.informativeText = "Install or update Viventium from a checkout outside Documents, Desktop, and Downloads, or explicitly choose a developer checkout with `bin/viventium runtime-checkout use --this --allow-protected-folder`."
        alert.alertStyle = .warning
        alert.addButton(withTitle: "OK")
        alert.runModal()
    }

    private func presentTranscriptIngestAlert(title: String, message: String) {
        let alert = NSAlert()
        alert.messageText = title
        alert.informativeText = message
        alert.alertStyle = .warning
        alert.addButton(withTitle: "OK")
        alert.runModal()
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
        guard !Self.configUsesProtectedRepoRoot(config) else {
            self.log("Auto-start skipped; helper is still bound to a protected-folder checkout")
            self.stackState = .unavailable("Protected Checkout")
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
            let snapshot = await Self.stackHealthSnapshot(runtime: runtime, appSupportDir: config.appSupportDir)
            if snapshot.healthy {
                await MainActor.run {
                    self.log("Auto-start skipped; stack already healthy (\(trigger))")
                    self.stackState = .running
                    self.didAttemptLaunchAutostart = true
                }
                return
            }
            if snapshot.needsAttention {
                await MainActor.run {
                    self.log("Auto-start skipped; stack needs attention (\(trigger))")
                    self.stackState = .needsAttention
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
        let configured = self.applyActiveRuntimeCheckout(decoded)
        let healed = self.healProtectedFolderBinding(configured)
        if healed != decoded {
            self.appendHelperLog(
                self.makeHelperLogURL(appSupportDir: healed.appSupportDir),
                self.configUsesProtectedRepoRoot(configured)
                    ? "Helper config repoRoot moved from a protected folder to a public-safe checkout"
                    : "Helper config repoRoot updated from the active runtime checkout setting"
            )
            _ = self.saveConfig(healed)
        } else if self.configUsesProtectedRepoRoot(decoded) {
            self.appendHelperLog(
                self.makeHelperLogURL(appSupportDir: decoded.appSupportDir),
                "Helper config repoRoot is inside a protected folder and no public-safe checkout was found"
            )
        } else if self.repoRootUsesMacOSProtectedFolderAccess(decoded.repoRoot) {
            self.appendHelperLog(
                self.makeHelperLogURL(appSupportDir: decoded.appSupportDir),
                "Helper config intentionally uses an active developer checkout inside a protected folder"
            )
        }
        return healed
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

    private static func healProtectedFolderBinding(_ config: HelperConfig) -> HelperConfig {
        if config.allowProtectedRepoRoot == true {
            return HelperConfig(
                repoRoot: self.normalizedFileSystemPath(config.repoRoot),
                appSupportDir: config.appSupportDir,
                allowProtectedRepoRoot: config.allowProtectedRepoRoot,
                showInStatusBar: config.showInStatusBar
            )
        }
        let resolvedRepoRoot = self.resolveSafeRuntimeRepoRoot(config.repoRoot)
        guard resolvedRepoRoot != config.repoRoot else {
            return config
        }
        return HelperConfig(
            repoRoot: resolvedRepoRoot,
            appSupportDir: config.appSupportDir,
            allowProtectedRepoRoot: false,
            showInStatusBar: config.showInStatusBar
        )
    }

    private static func applyActiveRuntimeCheckout(_ config: HelperConfig) -> HelperConfig {
        guard let activeCheckout = self.loadActiveRuntimeCheckout(appSupportDir: config.appSupportDir) else {
            return config
        }
        let normalizedRepoRoot = self.normalizedFileSystemPath(activeCheckout.repoRoot)
        guard self.isViventiumRuntimeRepoRoot(normalizedRepoRoot) else {
            return config
        }
        if self.repoRootUsesMacOSProtectedFolderAccess(normalizedRepoRoot),
           activeCheckout.allowProtectedFolderAccess != true
        {
            self.appendHelperLog(
                self.makeHelperLogURL(appSupportDir: config.appSupportDir),
                "Ignoring active runtime checkout because protected-folder access was not explicitly allowed"
            )
            return config
        }
        return HelperConfig(
            repoRoot: normalizedRepoRoot,
            appSupportDir: config.appSupportDir,
            allowProtectedRepoRoot: activeCheckout.allowProtectedFolderAccess == true,
            showInStatusBar: config.showInStatusBar
        )
    }

    private static func loadActiveRuntimeCheckout(appSupportDir: String) -> ActiveRuntimeCheckout? {
        let stateURL = URL(fileURLWithPath: appSupportDir, isDirectory: true)
            .appendingPathComponent("state/active-checkout.json")
        guard
            let data = try? Data(contentsOf: stateURL),
            let decoded = try? JSONDecoder().decode(ActiveRuntimeCheckout.self, from: data)
        else {
            return nil
        }
        return decoded
    }

    private static func configUsesProtectedRepoRoot(_ config: HelperConfig) -> Bool {
        self.repoRootUsesMacOSProtectedFolderAccess(config.repoRoot) &&
            config.allowProtectedRepoRoot != true
    }

    private static func resolveSafeRuntimeRepoRoot(_ repoRoot: String) -> String {
        let normalizedRepoRoot = self.normalizedFileSystemPath(repoRoot)
        guard self.repoRootUsesMacOSProtectedFolderAccess(normalizedRepoRoot) else {
            return normalizedRepoRoot
        }

        let homeDirectory = FileManager.default.homeDirectoryForCurrentUser.path
        let environment = ProcessInfo.processInfo.environment
        let candidates = [
            environment["VIVENTIUM_HELPER_RUNTIME_REPO_ROOT"],
            environment["VIVENTIUM_PUBLIC_INSTALL_DIR"],
            environment["VIVENTIUM_INSTALL_DIR"],
            "\(homeDirectory)/viventium",
        ].compactMap { $0?.trimmingCharacters(in: .whitespacesAndNewlines) }

        for candidate in candidates where !candidate.isEmpty {
            let normalizedCandidate = self.normalizedFileSystemPath(candidate)
            guard normalizedCandidate != normalizedRepoRoot else {
                continue
            }
            if self.isViventiumRuntimeRepoRoot(normalizedCandidate),
               !self.repoRootUsesMacOSProtectedFolderAccess(normalizedCandidate) {
                return normalizedCandidate
            }
        }

        return normalizedRepoRoot
    }

    private static func repoRootUsesMacOSProtectedFolderAccess(_ repoRoot: String) -> Bool {
        self.pathUsesMacOSProtectedFolderAccess(repoRoot)
    }

    private static func pathUsesMacOSProtectedFolderAccess(_ path: String) -> Bool {
        let homeDirectory = FileManager.default.homeDirectoryForCurrentUser.path
        let protectedRoots = [
            "\(homeDirectory)/Documents",
            "\(homeDirectory)/Desktop",
            "\(homeDirectory)/Downloads",
        ]
        return protectedRoots.contains { self.path(path, isWithin: $0) }
    }

    private static func path(_ candidate: String, isWithin parentDirectory: String) -> Bool {
        let normalizedCandidate = self.normalizedFileSystemPath(candidate)
        let normalizedParent = self.normalizedFileSystemPath(parentDirectory)
        return normalizedCandidate == normalizedParent ||
            normalizedCandidate.hasPrefix("\(normalizedParent)/")
    }

    private static func normalizedFileSystemPath(_ path: String) -> String {
        URL(fileURLWithPath: path, isDirectory: true)
            .standardizedFileURL
            .resolvingSymlinksInPath()
            .path
    }

    private static func isViventiumRuntimeRepoRoot(_ candidate: String) -> Bool {
        FileManager.default.isExecutableFile(atPath: "\(candidate)/bin/viventium") &&
            FileManager.default.fileExists(atPath: "\(candidate)/scripts/viventium/common.sh") &&
            FileManager.default.fileExists(atPath: "\(candidate)/viventium_v0_4/viventium-librechat-start.sh")
    }

    private static func transcriptIngestSourceStatus(config: HelperConfig) -> TranscriptIngestSourceStatus {
        let values = RuntimeEnvParser().readRuntimeValues(appSupportDir: config.appSupportDir)
        guard
            let rawSource = values["VIVENTIUM_MEMORY_TRANSCRIPTS_DIR"]?.trimmingCharacters(in: .whitespacesAndNewlines),
            !rawSource.isEmpty
        else {
            return .notConfigured
        }

        let sourcePath = (rawSource as NSString).expandingTildeInPath
        var isDirectory = ObjCBool(false)
        guard FileManager.default.fileExists(atPath: sourcePath, isDirectory: &isDirectory),
              isDirectory.boolValue
        else {
            return .unavailable
        }

        return .ready
    }

    private static func transcriptIngestScopeDescription(config: HelperConfig) -> String {
        let values = RuntimeEnvParser().readRuntimeValues(appSupportDir: config.appSupportDir)
        let scope = (values["VIVENTIUM_MEMORY_HARDENING_USER_EMAIL"] ?? "")
            .trimmingCharacters(in: .whitespacesAndNewlines)
        if scope.isEmpty {
            return "all opted-in local users"
        }
        return "account \(scope)"
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

    private nonisolated static func playgroundHealthy(port: Int) async -> Bool {
        guard let status = await self.firstHTTPStatus(urls: self.loopbackCandidateURLs(port: port, path: "/api/health")) else {
            return false
        }
        return (200..<400).contains(status)
    }

    private nonisolated static func stackHealthSnapshot(
        runtime: RuntimePorts,
        appSupportDir: String? = nil
    ) async -> StackHealthSnapshot {
        let apiReady = await self.apiHealthy(port: runtime.apiPort)
        let frontendReady = apiReady ? await self.frontendHealthy(port: runtime.frontendPort) : false
        // Voice-call deep links land on the dedicated modern playground. Probe it separately so
        // the helper can still prefer that surface when it is the only user-facing surface ready.
        let playgroundReady = await self.playgroundHealthy(port: runtime.playgroundPort)
        let optionalSurfacesReady = self.optionalSurfacesReady(
            runtime: runtime,
            appSupportDir: appSupportDir
        )
        return StackHealthSnapshot(
            apiReady: apiReady,
            frontendReady: frontendReady,
            playgroundReady: playgroundReady,
            optionalSurfacesReady: optionalSurfacesReady
        )
    }

    private nonisolated static func optionalSurfacesReady(runtime: RuntimePorts, appSupportDir: String?) -> Bool {
        guard let appSupportDir else {
            return true
        }
        if runtime.startTelegram {
            if !self.telegramBridgeRunning(runtime: runtime, appSupportDir: appSupportDir) {
                return false
            }
            if self.recentTelegramRuntimeIssue(
                logURLs: self.telegramLogURLs(runtime: runtime, appSupportDir: appSupportDir, names: ["telegram_bot.log"])
            ) {
                return false
            }
        }
        if runtime.startTelegramCodex && !self.telegramCodexRunning(runtime: runtime, appSupportDir: appSupportDir) {
            return false
        }
        return true
    }

    private nonisolated static func stackHealthy(apiPort: Int, frontendPort: Int, playgroundPort: Int) async -> Bool {
        await self.stackHealthSnapshot(
            runtime: RuntimePorts(
                apiPort: apiPort,
                frontendPort: frontendPort,
                playgroundPort: playgroundPort,
                runtimeProfile: "isolated",
                startTelegram: false,
                startTelegramCodex: false,
                managedStopCheckURLs: []
            )
        ).healthy
    }

    private nonisolated static func frontendURLString(host: String, port: Int) -> String {
        "http://\(host):\(port)"
    }

    private nonisolated static func preferredOpenURLString(
        runtime: RuntimePorts,
        host: String,
        snapshot: StackHealthSnapshot
    ) -> String {
        if snapshot.healthy {
            return self.frontendURLString(host: host, port: runtime.frontendPort)
        }
        if snapshot.preferredSurfaceIsPlaygroundOnly {
            return self.frontendURLString(host: host, port: runtime.playgroundPort)
        }
        return self.frontendURLString(host: host, port: runtime.frontendPort)
    }

    private nonisolated static func preferredOpenURLString(runtime: RuntimePorts, host: String) async -> String {
        let snapshot = await self.stackHealthSnapshot(runtime: runtime)
        return self.preferredOpenURLString(runtime: runtime, host: host, snapshot: snapshot)
    }

    private nonisolated static func userFacingSurfaceHealthy(runtime: RuntimePorts) async -> Bool {
        await self.stackHealthSnapshot(runtime: runtime).healthy
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
            repoRoot: repoRoot,
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

    private nonisolated static func rotateHelperLogIfNeeded(_ url: URL, maxBytes: UInt64 = 25 * 1024 * 1024) {
        guard self.fileSize(url) > maxBytes else {
            return
        }
        let rotatedURL = url.deletingPathExtension()
            .appendingPathExtension("previous")
            .appendingPathExtension(url.pathExtension)
        try? FileManager.default.removeItem(at: rotatedURL)
        try? FileManager.default.moveItem(at: url, to: rotatedURL)
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
        standardInput: String? = nil,
        timeoutSeconds: TimeInterval? = nil
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
            if let timeoutSeconds {
                let deadline = Date().addingTimeInterval(timeoutSeconds)
                while process.isRunning && Date() < deadline {
                    Thread.sleep(forTimeInterval: 0.05)
                }
                if process.isRunning {
                    process.terminate()
                    let terminationDeadline = Date().addingTimeInterval(1.0)
                    while process.isRunning && Date() < terminationDeadline {
                        Thread.sleep(forTimeInterval: 0.05)
                    }
                    if process.isRunning {
                        Darwin.kill(process.processIdentifier, SIGKILL)
                    }
                    process.waitUntilExit()
                    return (124, "", "Timed out after \(Int(timeoutSeconds))s")
                }
            }
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

    private nonisolated static func launchAtLoginFastPathEnabled() -> Bool {
        FileManager.default.fileExists(atPath: self.launchAgentPlistURL().path)
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
            standardInput: script,
            timeoutSeconds: 5
        )
        guard result.status == 0 else {
            return false
        }
        return result.stdout.trimmingCharacters(in: .whitespacesAndNewlines) == "true"
    }

    private nonisolated static func launchAtLoginIsEnabled() -> Bool {
        self.launchAtLoginFastPathEnabled() || self.loginItemExists()
    }

    private nonisolated static func removeLaunchAgent() {
        let plistURL = self.launchAgentPlistURL()
        _ = self.runSystemProcess(
            executableURL: URL(fileURLWithPath: "/bin/launchctl"),
            arguments: ["bootout", "gui/\(getuid())", plistURL.path],
            timeoutSeconds: 5
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
            standardInput: script,
            timeoutSeconds: 5
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
            standardInput: script,
            timeoutSeconds: 5
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
        repoRoot: String,
        appSupportDir: String,
        logFileName: String
    ) -> Int32? {
        self.submitDetachedHelperStackCommand(
            repoRoot: repoRoot,
            appSupportDir: appSupportDir,
            logFileName: logFileName,
            pidFileName: "helper-detached-start.pid",
            commandArguments: ["launch"],
            environmentOverrides: ["VIVENTIUM_DETACHED_START": "true"]
        )
    }

    private nonisolated static func submitDetachedStop(
        repoRoot: String,
        appSupportDir: String,
        logFileName: String,
    ) -> Int32? {
        self.submitDetachedHelperStackCommand(
            repoRoot: repoRoot,
            appSupportDir: appSupportDir,
            logFileName: logFileName,
            pidFileName: "helper-detached-stop.pid",
            commandArguments: ["stop"],
            environmentOverrides: ["VIVENTIUM_HELPER_STOP_BACKGROUND_NATIVE": "1"]
        )
    }

    private nonisolated static func submitDetachedHelperStackCommand(
        repoRoot: String,
        appSupportDir: String,
        logFileName: String,
        pidFileName: String,
        commandArguments: [String],
        environmentOverrides: [String: String]
    ) -> Int32? {
        let binViventiumPath = "\(repoRoot)/bin/viventium"
        guard FileManager.default.isExecutableFile(atPath: binViventiumPath) else {
            return nil
        }
        let logURL = Self.makeNamedHelperLogURL(appSupportDir: appSupportDir, logFileName: logFileName)
        self.rotateHelperLogIfNeeded(logURL)
        let logPath = logURL.path
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
        let escapedCommand = (["/bin/bash", binViventiumPath, "--app-support-dir", appSupportDir] + commandArguments)
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
        process.environment = self.makeHelperStackEnvironment(
            repoRoot: repoRoot,
            appSupportDir: appSupportDir,
            environmentOverrides: environmentOverrides
        )
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

    private nonisolated static func makeHelperStackEnvironment(
        repoRoot: String,
        appSupportDir: String,
        environmentOverrides: [String: String]
    ) -> [String: String] {
        var environment = self.makeCLIEnvironment()
        environment["VIVENTIUM_HELPER_V0_ROOT"] = "\(repoRoot)/viventium_v0_4"
        environment["VIVENTIUM_HELPER_CORE_ROOT"] = repoRoot
        environment["VIVENTIUM_HELPER_WORKSPACE_ROOT"] = URL(fileURLWithPath: repoRoot, isDirectory: true)
            .deletingLastPathComponent()
            .path
        environment["VIVENTIUM_APP_SUPPORT_DIR"] = appSupportDir
        environment["VIVENTIUM_ENV_FILE"] = "\(appSupportDir)/runtime/runtime.env"
        environment["VIVENTIUM_ENV_LOCAL_FILE"] = "\(appSupportDir)/runtime/runtime.local.env"
        for (key, value) in environmentOverrides {
            environment[key] = value
        }
        return environment
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

    private nonisolated static func runCLICaptured(
        repoRoot: String,
        appSupportDir: String,
        arguments: [String],
        logFileName: String? = nil,
        timeoutSeconds: TimeInterval? = nil
    ) -> (exitStatus: Int32, stdout: String) {
        let process = self.makeCLIProcess(
            repoRoot: repoRoot,
            appSupportDir: appSupportDir,
            arguments: arguments,
            logFileName: logFileName
        )
        let stdoutURL = URL(fileURLWithPath: NSTemporaryDirectory(), isDirectory: true)
            .appendingPathComponent("viventium-helper-cli-\(UUID().uuidString).json")
        FileManager.default.createFile(atPath: stdoutURL.path, contents: nil)
        let stdoutHandle = try? FileHandle(forWritingTo: stdoutURL)
        process.standardOutput = stdoutHandle ?? FileHandle.nullDevice
        defer {
            try? stdoutHandle?.close()
            try? FileManager.default.removeItem(at: stdoutURL)
        }
        do {
            try process.run()
            if let timeoutSeconds {
                let deadline = Date().addingTimeInterval(timeoutSeconds)
                while process.isRunning && Date() < deadline {
                    Thread.sleep(forTimeInterval: 0.05)
                }
                if process.isRunning {
                    process.terminate()
                    process.waitUntilExit()
                    return (124, "")
                }
            }
            process.waitUntilExit()
            try? stdoutHandle?.close()
            let stdout = (try? String(contentsOf: stdoutURL, encoding: .utf8)) ?? ""
            return (process.terminationStatus, stdout)
        } catch {
            return (-1, "")
        }
    }

    private struct UpdateCheckSummary {
        let title: String
        let message: String
        let updateAvailable: Bool
        let blockers: [String]
    }

    private nonisolated static func updateCheckSummary(stdout: String) -> UpdateCheckSummary {
        guard
            let root = self.parseJSONObject(stdout)
        else {
            return UpdateCheckSummary(
                title: "Could not read update check",
                message: "The update check did not return readable status.",
                updateAvailable: false,
                blockers: ["invalid_json"]
            )
        }
        let updateAvailable = (root["update_available"] as? Bool) ?? false
        let blockers = (root["blockers"] as? [String]) ?? []
        if !blockers.isEmpty {
            return UpdateCheckSummary(
                title: "Update blocked",
                message: "Viventium found blockers: \(blockers.joined(separator: ", ")). Resolve them, then check again.",
                updateAvailable: updateAvailable,
                blockers: blockers
            )
        }
        if updateAvailable {
            let behind = (root["commits_behind"] as? Int) ?? 0
            return UpdateCheckSummary(
                title: "Update available",
                message: "Viventium is \(behind) commit(s) behind the configured upstream branch.",
                updateAvailable: true,
                blockers: []
            )
        }
        return UpdateCheckSummary(
            title: "Viventium is up to date",
            message: "No updates were found for the current branch.",
            updateAvailable: false,
            blockers: []
        )
    }

    private nonisolated static func parseJSONObject(_ stdout: String) -> [String: Any]? {
        guard
            let data = stdout.data(using: .utf8),
            let root = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        else {
            return nil
        }
        return root
    }

    private nonisolated static func workflowStatusLabel(appSupportDir: String) -> String? {
        let activeURL = URL(fileURLWithPath: appSupportDir, isDirectory: true)
            .appendingPathComponent("state/workflows/active.json")
        guard
            let activeData = try? Data(contentsOf: activeURL),
            let active = try? JSONSerialization.jsonObject(with: activeData) as? [String: Any],
            let runDir = active["run_dir"] as? String
        else {
            return nil
        }
        let summaryURL = URL(fileURLWithPath: runDir, isDirectory: true).appendingPathComponent("summary.json")
        guard
            let summaryData = try? Data(contentsOf: summaryURL),
            let summary = try? JSONSerialization.jsonObject(with: summaryData) as? [String: Any]
        else {
            return nil
        }
        let state = (summary["state"] as? String) ?? ""
        guard ["queued", "running", "degraded_ready", "awaiting_approval"].contains(state) else {
            return nil
        }
        let workflow = (summary["workflow"] as? String) ?? ""
        let phase = (summary["phase"] as? String) ?? "intake"
        let startedAt = (summary["started_at"] as? String) ?? ""
        let minutes = self.elapsedMinutes(sinceISO8601: startedAt)
        if workflow == "feature-request" {
            if state == "awaiting_approval" {
                return "Feature Ready"
            }
            if phase == "implementation" {
                return "Building Feature (\(minutes) mins passed)"
            }
            return "Feature Intake (\(minutes) mins passed)"
        }
        if workflow == "bug-report" {
            if state == "awaiting_approval" {
                return "Bug Report Ready"
            }
            if phase == "implementation" {
                return "Fixing Bug (\(minutes) mins passed)"
            }
            return "Bug Intake (\(minutes) mins passed)"
        }
        return "Healing (\(minutes) mins passed)"
    }

    private nonisolated static func elapsedMinutes(sinceISO8601 value: String) -> Int {
        let formatter = ISO8601DateFormatter()
        guard let date = formatter.date(from: value) else {
            return 0
        }
        return max(0, Int(Date().timeIntervalSince(date) / 60.0))
    }

    @discardableResult
    private nonisolated static func runCLIStatusOnly(
        repoRoot: String,
        appSupportDir: String,
        arguments: [String],
        environmentOverrides: [String: String] = [:]
    ) -> Int32 {
        let process = self.makeCLIProcess(
            repoRoot: repoRoot,
            appSupportDir: appSupportDir,
            arguments: arguments,
            environmentOverrides: environmentOverrides
        )
        process.standardOutput = FileHandle.nullDevice
        process.standardError = FileHandle.nullDevice
        do {
            try process.run()
            process.waitUntilExit()
            return process.terminationStatus
        } catch {
            return -1
        }
    }

    @discardableResult
    private nonisolated static func runMemoryHardeningStatusOnly(
        repoRoot: String,
        appSupportDir: String,
        arguments: [String],
        environmentOverrides: [String: String] = [:]
    ) -> Int32 {
        self.runMemoryHardeningCaptured(
            repoRoot: repoRoot,
            appSupportDir: appSupportDir,
            arguments: arguments,
            environmentOverrides: environmentOverrides
        ).exitStatus
    }

    private nonisolated static func runMemoryHardeningCaptured(
        repoRoot: String,
        appSupportDir: String,
        arguments: [String],
        environmentOverrides: [String: String] = [:]
    ) -> CommandCaptureResult {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/env")
        process.currentDirectoryURL = URL(fileURLWithPath: repoRoot, isDirectory: true)
        process.arguments = [
            "python3",
            "\(repoRoot)/scripts/viventium/memory_harden.py",
            "--repo-root",
            repoRoot,
            "--app-support-dir",
            appSupportDir,
            "--runtime-dir",
            "\(appSupportDir)/runtime",
        ] + arguments
        var environment = self.makeCLIEnvironment()
        environment["PWD"] = repoRoot
        environment["VIVENTIUM_APP_SUPPORT_DIR"] = appSupportDir
        environment["VIVENTIUM_ENV_FILE"] = "\(appSupportDir)/runtime/runtime.env"
        environment["VIVENTIUM_ENV_LOCAL_FILE"] = "\(appSupportDir)/runtime/runtime.local.env"
        for (key, value) in environmentOverrides {
            environment[key] = value
        }
        process.environment = environment
        process.standardInput = FileHandle.nullDevice
        let stdoutURL = URL(fileURLWithPath: NSTemporaryDirectory(), isDirectory: true)
            .appendingPathComponent("viventium-helper-memory-\(UUID().uuidString).json")
        FileManager.default.createFile(atPath: stdoutURL.path, contents: nil)
        let stdoutHandle = try? FileHandle(forWritingTo: stdoutURL)
        process.standardOutput = stdoutHandle ?? FileHandle.nullDevice
        process.standardError = FileHandle.nullDevice
        defer {
            try? stdoutHandle?.close()
            try? FileManager.default.removeItem(at: stdoutURL)
        }
        do {
            try process.run()
            process.waitUntilExit()
            try? stdoutHandle?.close()
            let stdout = (try? String(contentsOf: stdoutURL, encoding: .utf8)) ?? ""
            return CommandCaptureResult(exitStatus: process.terminationStatus, stdout: stdout)
        } catch {
            return CommandCaptureResult(exitStatus: -1, stdout: "")
        }
    }

    private struct TranscriptIngestSummary {
        let message: String
        let skipped: Bool
        let incomplete: Bool
    }

    private nonisolated static func transcriptIngestRunSummary(stdout: String) -> TranscriptIngestSummary? {
        guard
            let data = stdout.data(using: .utf8),
            let root = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        else {
            return nil
        }

        let users = root["users"] as? [[String: Any]] ?? []
        let skippedReasons = users.compactMap { user -> String? in
            let status = (user["status"] as? String) ?? ""
            let reason = (user["reason"] as? String) ?? ""
            if status == "skipped" && !reason.isEmpty {
                return reason
            }
            return nil
        }
        let transcriptStats = users.compactMap { $0["transcript_ingest"] as? [String: Any] }
        let aggregateStatus = (root["status"] as? String) ?? ""
        let aggregateSkippedByCap = self.intValue(root["files_skipped_by_cap"])
        let filesSeen = transcriptStats.reduce(0) { $0 + self.intValue($1["files_seen"]) }
        let filesPendingBeforeRun = transcriptStats.reduce(0) { $0 + self.intValue($1["files_pending"]) }
        let filesDeferredByCap = transcriptStats.reduce(0) { $0 + self.intValue($1["files_skipped_by_cap"]) }
        let applyResults = root["apply_results"] as? [[String: Any]] ?? []
        let vectorStats = applyResults.compactMap { $0["transcript_vectors"] as? [String: Any] }
        let uploaded = vectorStats.reduce(0) { $0 + self.intValue($1["uploaded"]) }
        let deleted = vectorStats.reduce(0) { $0 + self.intValue($1["deleted"]) }

        var parts: [String] = []
        if transcriptStats.isEmpty && !skippedReasons.isEmpty {
            let uniqueReasons = Array(Set(skippedReasons)).sorted().joined(separator: ", ")
            parts.append("No transcript scan ran: \(uniqueReasons)")
        }
        if filesSeen > 0 {
            parts.append("\(filesSeen) source files checked")
        }
        if filesPendingBeforeRun > 0 {
            parts.append("\(filesPendingBeforeRun) pending at start")
        }
        if uploaded > 0 {
            parts.append("\(uploaded) transcript summaries uploaded")
        }
        if deleted > 0 {
            parts.append("\(deleted) stale transcript artifacts removed")
        }
        if filesDeferredByCap > 0 {
            parts.append("\(filesDeferredByCap) files deferred by caps; run ingest again or let the 3am job continue")
        } else if filesSeen > 0 {
            parts.append("0 files deferred by caps")
        }
        return parts.isEmpty
            ? nil
            : TranscriptIngestSummary(
                message: parts.joined(separator: "; "),
                skipped: transcriptStats.isEmpty && !skippedReasons.isEmpty,
                incomplete: aggregateStatus == "partial" || aggregateSkippedByCap > 0 || filesDeferredByCap > 0
            )
    }

    private nonisolated static func intValue(_ value: Any?) -> Int {
        if let value = value as? Int {
            return value
        }
        if let value = value as? NSNumber {
            return value.intValue
        }
        if let value = value as? String {
            return Int(value) ?? 0
        }
        return 0
    }

    private nonisolated static func latestSnapshotPath(appSupportDir: String) -> String? {
        let latestPathURL = URL(fileURLWithPath: appSupportDir, isDirectory: true)
            .appendingPathComponent("snapshots/LATEST_PATH")
        guard
            let data = try? Data(contentsOf: latestPathURL),
            let value = String(data: data, encoding: .utf8)?
                .trimmingCharacters(in: .whitespacesAndNewlines),
            !value.isEmpty
        else {
            return nil
        }
        return value
    }

    private func openBrowser(path: String? = nil) {
        guard let baseURL = URL(string: self.openURLString) else { return }
        let url = path.map {
            baseURL.appendingPathComponent($0.trimmingCharacters(in: CharacterSet(charactersIn: "/")))
        } ?? baseURL
        NSWorkspace.shared.open(url)
    }
}

private struct RuntimePorts: Equatable {
    let apiPort: Int
    let frontendPort: Int
    let playgroundPort: Int
    let runtimeProfile: String
    let startTelegram: Bool
    let startTelegramCodex: Bool
    let managedStopCheckURLs: [String]
}

private struct RuntimeEnvParser {
    func readRuntime(appSupportDir: String) -> RuntimePorts {
        let values = self.readRuntimeValues(appSupportDir: appSupportDir)
        let apiPort = Int(values["VIVENTIUM_LC_API_PORT"] ?? "") ?? 3180
        let frontendPort = Int(values["VIVENTIUM_LC_FRONTEND_PORT"] ?? "") ?? 3190
        let playgroundPort = Int(values["VIVENTIUM_PLAYGROUND_PORT"] ?? "") ?? 3300
        let runtimeProfile = values["VIVENTIUM_RUNTIME_PROFILE"] ?? "isolated"
        return RuntimePorts(
            apiPort: apiPort,
            frontendPort: frontendPort,
            playgroundPort: playgroundPort,
            runtimeProfile: runtimeProfile,
            startTelegram: self.boolValue(values["START_TELEGRAM"]),
            startTelegramCodex: self.boolValue(values["START_TELEGRAM_CODEX"]),
            managedStopCheckURLs: self.managedStopCheckURLs(values: values)
        )
    }

    func readRuntimeValues(appSupportDir: String) -> [String: String] {
        let runtimeDir = "\(appSupportDir)/runtime"
        var values = self.parseFile("\(runtimeDir)/runtime.env")
        let localValues = self.parseFile("\(runtimeDir)/runtime.local.env")
        for (key, value) in localValues {
            values[key] = value
        }
        return values
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
        return !self.anyTelegramBridgeRunning(runtime: runtime, appSupportDir: appSupportDir)
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
        expectedRepoRoot: String,
        knownSnapshot: StackHealthSnapshot? = nil
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

        if knownSnapshot?.healthy == true {
            return true
        }
        if knownSnapshot == nil, await self.userFacingSurfaceHealthy(runtime: runtime) {
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
        self.telegramPidRunning(runtime: runtime, appSupportDir: appSupportDir, names: ["telegram_bot.pid"])
    }

    nonisolated static func telegramCodexRunning(runtime: RuntimePorts, appSupportDir: String) -> Bool {
        self.telegramPidRunning(runtime: runtime, appSupportDir: appSupportDir, names: ["telegram_codex.pid"])
    }

    nonisolated static func anyTelegramBridgeRunning(runtime: RuntimePorts, appSupportDir: String) -> Bool {
        self.telegramPidRunning(runtime: runtime, appSupportDir: appSupportDir, names: ["telegram_bot.pid", "telegram_codex.pid"])
    }

    nonisolated static func telegramPidRunning(runtime: RuntimePorts, appSupportDir: String, names: [String]) -> Bool {
        let runtimeRoot = URL(fileURLWithPath: appSupportDir, isDirectory: true)
            .appendingPathComponent("state/runtime/\(runtime.runtimeProfile)", isDirectory: true)
        let legacyLogRoot = runtimeRoot.appendingPathComponent("logs", isDirectory: true)
        let knownPidFilesByName: [String: [URL]] = [
            "telegram_bot.pid": [
                runtimeRoot.appendingPathComponent("telegram_bot.pid"),
                legacyLogRoot.appendingPathComponent("telegram_bot.pid"),
            ],
            "telegram_codex.pid": [
                runtimeRoot.appendingPathComponent("telegram_codex.pid"),
                legacyLogRoot.appendingPathComponent("telegram_codex.pid"),
            ],
        ]
        let pidFiles = names.flatMap { name -> [URL] in
            knownPidFilesByName[name] ?? [
                runtimeRoot.appendingPathComponent(name),
                legacyLogRoot.appendingPathComponent(name),
            ]
        }
        return pidFiles.contains { self.pidFileProcessRunning($0) }
    }

    nonisolated static func telegramLogURLs(runtime: RuntimePorts, appSupportDir: String, names: [String]) -> [URL] {
        let runtimeRoot = URL(fileURLWithPath: appSupportDir, isDirectory: true)
            .appendingPathComponent("state/runtime/\(runtime.runtimeProfile)", isDirectory: true)
        let legacyLogRoot = runtimeRoot.appendingPathComponent("logs", isDirectory: true)
        return names.flatMap { name -> [URL] in
            [
                runtimeRoot.appendingPathComponent(name),
                legacyLogRoot.appendingPathComponent(name),
            ]
        }
    }

    nonisolated static func recentTelegramRuntimeIssue(logURLs: [URL]) -> Bool {
        let issueNeedles = [
            "terminated by other getupdates request",
            "conflict:",
            "only one bot instance",
            "credentials rejected",
            "connected-account refresh failed",
            "invalid_api_key",
            "authenticationerror",
            "unauthorized",
        ]
        let recoveryMarkers = [
            "starting polling mode",
            "application started",
            "telegram bot started",
        ]
        for url in logURLs {
            guard var text = self.recentFileText(url, maxBytes: 65_536)?.lowercased(), !text.isEmpty else {
                continue
            }
            let latestRecovery = recoveryMarkers
                .compactMap { text.range(of: $0, options: .backwards)?.lowerBound }
                .max()
            if let latestRecovery {
                text = String(text[latestRecovery...])
            }
            if issueNeedles.contains(where: { text.contains($0) }) {
                return true
            }
        }
        return false
    }

    nonisolated static func recentFileText(_ url: URL, maxBytes: UInt64) -> String? {
        guard let handle = try? FileHandle(forReadingFrom: url) else {
            return nil
        }
        defer {
            try? handle.close()
        }
        let size = (try? handle.seekToEnd()) ?? 0
        try? handle.seek(toOffset: size > maxBytes ? size - maxBytes : 0)
        guard let data = try? handle.readToEnd(), !data.isEmpty else {
            return nil
        }
        return String(data: data, encoding: .utf8)
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
            Button("Open Feelings") {
                self.controller.openFeelings()
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
            Menu("Advanced") {
                Button("Check for Updates...") {
                    self.controller.checkForUpdates()
                }
                .help("Look for Viventium updates, show blockers, and ask before installing anything.")
                .disabled(self.controller.workflowActionDisabled)
                Menu(self.controller.promptWorkbenchMenuTitle) {
                    Button("Open") {
                        self.controller.openPromptWorkbench()
                    }
                    .help("Start Prompt Workbench if needed, then open it in your browser.")
                    .disabled(self.controller.promptWorkbenchActionDisabled)
                    Button("Start") {
                        self.controller.startPromptWorkbench()
                    }
                    .help("Start only the local Prompt Workbench web app.")
                    .disabled(self.controller.promptWorkbenchActionDisabled)
                    Button("Stop") {
                        self.controller.stopPromptWorkbench()
                    }
                    .help("Stop only the Prompt Workbench web app; the Viventium runtime keeps its current state.")
                    .disabled(self.controller.promptWorkbenchActionDisabled)
                }
                .disabled(self.controller.promptWorkbenchActionDisabled)
                Button(self.controller.backupActionLabel) {
                    self.controller.createBackupSnapshot()
                }
                .help("Create a local backup snapshot before risky changes or troubleshooting.")
                .disabled(self.controller.backupActionDisabled)
                Divider()
                Button("Heal Viventium...") {
                    self.controller.startHealWorkflow()
                }
                .help("Ask the local AI workflow to diagnose Viventium from logs, code, state, and docs.")
                .disabled(self.controller.workflowActionDisabled)
                Button("Report a Bug...") {
                    self.controller.startBugReportWorkflow()
                }
                .help("Collect what happened, reproduction steps, expected behavior, and actual behavior before a fix starts.")
                .disabled(self.controller.workflowActionDisabled)
                Button("Request a Feature...") {
                    self.controller.startFeatureRequestWorkflow()
                }
                .help("Collect success criteria and edge cases before building a requested feature.")
                .disabled(self.controller.workflowActionDisabled)
                Button("Approve Build or Fix...") {
                    self.controller.approveFeatureWorkflow()
                }
                .help("Approve the prepared feature or bug report and create an isolated local worktree.")
                .disabled(self.controller.workflowActionDisabled)
                Button("Cancel Active Workflow") {
                    self.controller.cancelWorkflow()
                }
                .help("Stop showing the current local workflow as active and clean safe temporary worktrees.")
                .disabled(self.controller.workflowActionDisabled)
                Button("Open Work Artifacts") {
                    self.controller.openWorkflowArtifacts()
                }
                .help("Open private local workflow files for the active heal, bug, or feature run.")
                .disabled(self.controller.workflowActionDisabled)
                Divider()
                Button(self.controller.transcriptIngestActionLabel) {
                    self.controller.ingestMeetingTranscripts()
                }
                .help("Import local meeting transcripts into Viventium memory when configured.")
                .disabled(self.controller.transcriptIngestActionDisabled)
                Button(self.controller.transcriptSourceActionLabel) {
                    self.controller.chooseTranscriptsFolder()
                }
                .help("Choose the local folder where Viventium reads meeting transcripts.")
                .disabled(self.controller.transcriptSourceActionDisabled)
                Divider()
                Toggle(
                    "Start Viventium at Login",
                    isOn: Binding(
                        get: { self.controller.launchAtLoginEnabled },
                        set: { self.controller.setLaunchAtLogin($0) }
                    )
                )
                .help("Start the Viventium helper automatically when you sign in to macOS.")
                Toggle(
                    "Show Status Bar Icon",
                    isOn: Binding(
                        get: { self.controller.showInStatusBarEnabled },
                        set: { self.controller.setShowInStatusBar($0) }
                    )
                )
                .help("Keep the Viventium menu visible in the macOS status bar.")
            }
            Divider()
            Button("Quit") {
                self.controller.quit()
            }
            .disabled(self.controller.actionDisabled)
        } label: {
            Text(self.controller.menuGlyph)
                .font(.system(size: 13, weight: .bold, design: .rounded))
        }

        Settings {
            EmptyView()
        }
    }
}

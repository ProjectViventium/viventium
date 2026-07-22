import AppKit
import Darwin
import Foundation

// Every mode executes only the signed bundled interpreter at
// Contents/Resources/runtime/python/bin/python3. PATH and system Python are never consulted.
private struct BundledInstaller {
    let resources: URL
    let python: URL
    let installer: URL

    static func load() -> BundledInstaller? {
        let resources = Bundle.main.bundleURL
            .appendingPathComponent("Contents/Resources", isDirectory: true)
        let python = resources
            .appendingPathComponent("runtime/python/bin/python3", isDirectory: false)
        let installer = resources
            .appendingPathComponent("scripts/install_native_payload.py", isDirectory: false)
        guard FileManager.default.isExecutableFile(atPath: python.path),
              FileManager.default.isReadableFile(atPath: installer.path) else {
            return nil
        }
        return BundledInstaller(resources: resources, python: python, installer: installer)
    }

    func process(arguments: [String]) -> Process {
        let process = Process()
        process.executableURL = python
        process.arguments = ["-E", "-s", "-B", installer.path] + arguments
        process.currentDirectoryURL = resources
        var environment = ProcessInfo.processInfo.environment.filter {
            !$0.key.hasPrefix("PYTHON")
        }
        environment["PYTHONNOUSERSITE"] = "1"
        process.environment = environment
        return process
    }
}

private func runHeadless(arguments: [String]) -> Int32 {
    guard let bundled = BundledInstaller.load() else {
        FileHandle.standardError.write(Data("Viventium Bootstrap is incomplete.\n".utf8))
        return 2
    }

    let process = bundled.process(arguments: arguments)
    do {
        try process.run()
        process.waitUntilExit()
        return process.terminationStatus
    } catch {
        FileHandle.standardError.write(Data("Viventium Bootstrap could not start.\n".utf8))
        return 2
    }
}

private final class BootstrapWindowController: NSObject, NSWindowDelegate {
    private let window: NSWindow
    private let stageLabel = NSTextField(labelWithString: "Preparing Easy Install…")
    private let detailLabel = NSTextField(wrappingLabelWithString: "")
    private let progress = NSProgressIndicator()
    private let primaryButton = NSButton()
    private let secondaryButton = NSButton()
    private let cancelButton = NSButton()

    private var installerProcess: Process?
    private var cancelRequested = false
    private var cancelEscalation: DispatchWorkItem?
    private var cancelKillEscalation: DispatchWorkItem?

    override init() {
        window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 560, height: 330),
            styleMask: [.titled, .closable],
            backing: .buffered,
            defer: false
        )
        super.init()
        configureWindow()
    }

    func showAndStart() {
        window.center()
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        startInstallation()
    }

    func requestApplicationTermination() -> Bool {
        guard installerProcess?.isRunning == true else { return true }
        requestCancel()
        return false
    }

    func windowShouldClose(_ sender: NSWindow) -> Bool {
        requestApplicationTermination()
    }

    private func configureWindow() {
        window.title = "Easy Install Viventium"
        window.delegate = self
        window.isReleasedWhenClosed = false
        window.tabbingMode = .disallowed
        window.collectionBehavior = [.moveToActiveSpace]

        let titleLabel = NSTextField(labelWithString: "Easy Install Viventium")
        titleLabel.font = NSFont.systemFont(ofSize: 25, weight: .semibold)
        titleLabel.textColor = .labelColor
        titleLabel.setAccessibilityLabel("Easy Install Viventium")

        let introLabel = NSTextField(
            wrappingLabelWithString: "Viventium verifies and installs its signed local release. Your personal files and account secrets are not shown here."
        )
        introLabel.font = NSFont.systemFont(ofSize: 14)
        introLabel.textColor = .secondaryLabelColor
        introLabel.maximumNumberOfLines = 3
        introLabel.setAccessibilityLabel("Easy Install description")

        stageLabel.font = NSFont.systemFont(ofSize: 15, weight: .medium)
        stageLabel.textColor = .labelColor
        stageLabel.maximumNumberOfLines = 2
        stageLabel.setAccessibilityLabel("Installation status")
        stageLabel.setAccessibilityHelp("The current Easy Install stage")

        detailLabel.font = NSFont.systemFont(ofSize: 13)
        detailLabel.textColor = .secondaryLabelColor
        detailLabel.maximumNumberOfLines = 3
        detailLabel.setAccessibilityLabel("Installation detail")
        detailLabel.setAccessibilityHelp("A short, privacy-safe explanation of the current stage")

        progress.controlSize = .regular
        progress.style = .bar
        progress.minValue = 0
        progress.maxValue = 1
        progress.setAccessibilityLabel("Easy Install progress")
        progress.setAccessibilityHelp("Installation is in progress")
        if NSWorkspace.shared.accessibilityDisplayShouldReduceMotion {
            progress.isIndeterminate = false
            progress.doubleValue = 0.35
        } else {
            progress.isIndeterminate = true
        }

        primaryButton.bezelStyle = .rounded
        primaryButton.target = self
        primaryButton.action = #selector(performPrimaryAction)
        primaryButton.keyEquivalent = "\r"
        primaryButton.setAccessibilityLabel("Primary Easy Install action")

        secondaryButton.bezelStyle = .rounded
        secondaryButton.target = self
        secondaryButton.action = #selector(quit)
        secondaryButton.title = "Quit"
        secondaryButton.setAccessibilityLabel("Quit Viventium Bootstrap")
        secondaryButton.setAccessibilityHelp("Close this installer")

        cancelButton.bezelStyle = .rounded
        cancelButton.target = self
        cancelButton.action = #selector(requestCancel)
        cancelButton.title = "Cancel"
        cancelButton.keyEquivalent = "\u{1b}"
        cancelButton.setAccessibilityLabel("Cancel Easy Install")
        cancelButton.setAccessibilityHelp("Request a safe stop and preserve the last known-good installation")

        let buttonSpacer = NSView()
        let buttonRow = NSStackView(views: [buttonSpacer, secondaryButton, primaryButton, cancelButton])
        buttonRow.orientation = .horizontal
        buttonRow.alignment = .centerY
        buttonRow.spacing = 10
        buttonSpacer.setContentHuggingPriority(.defaultLow, for: .horizontal)
        buttonSpacer.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)

        let content = NSStackView(views: [titleLabel, introLabel, stageLabel, progress, detailLabel, buttonRow])
        content.orientation = .vertical
        content.alignment = .leading
        content.spacing = 14
        content.edgeInsets = NSEdgeInsets(top: 28, left: 30, bottom: 24, right: 30)
        content.translatesAutoresizingMaskIntoConstraints = false
        window.contentView = content
        NSLayoutConstraint.activate([
            content.widthAnchor.constraint(equalToConstant: 560),
            content.heightAnchor.constraint(greaterThanOrEqualToConstant: 310),
            progress.widthAnchor.constraint(equalTo: content.widthAnchor, constant: -60),
            buttonRow.widthAnchor.constraint(equalTo: progress.widthAnchor),
        ])
    }

    private func updateStatus(stage: String, detail: String, announce: Bool = true) {
        stageLabel.stringValue = stage
        detailLabel.stringValue = detail
        guard announce else { return }
        NSAccessibility.post(
            element: stageLabel,
            notification: .announcementRequested,
            userInfo: [
                .announcement: stage,
                .priority: NSAccessibilityPriorityLevel.high.rawValue,
            ]
        )
    }

    private func startInstallation() {
        guard installerProcess?.isRunning != true else { return }
        cancelEscalation?.cancel()
        cancelKillEscalation?.cancel()
        cancelRequested = false
        setRunningState()

        guard let bundled = BundledInstaller.load() else {
            showFailure(
                stage: "Easy Install cannot start",
                detail: "This installer is incomplete. Download a fresh Viventium installer and try again."
            )
            return
        }

        let process = bundled.process(arguments: [])
        process.standardOutput = FileHandle.nullDevice
        process.standardError = FileHandle.nullDevice
        process.terminationHandler = { [weak self] finished in
            let status = finished.terminationStatus
            DispatchQueue.main.async {
                self?.finishInstallation(status: status)
            }
        }
        installerProcess = process

        do {
            try process.run()
            updateStatus(
                stage: "Installing Viventium…",
                detail: "This can take several minutes. You can keep using your Mac while Easy Install finishes."
            )
        } catch {
            installerProcess = nil
            showFailure(
                stage: "Easy Install could not begin",
                detail: "Nothing was activated. Try again, or download a fresh Viventium installer if this continues."
            )
        }
    }

    private func setRunningState() {
        updateStatus(
            stage: "Preparing a verified installation…",
            detail: "Easy Install keeps the last known-good version available until the new one passes its health checks.",
            announce: false
        )
        primaryButton.isHidden = true
        secondaryButton.isHidden = true
        cancelButton.isHidden = false
        cancelButton.isEnabled = true
        cancelButton.title = "Cancel"
        if progress.isIndeterminate {
            progress.startAnimation(nil)
        }
        progress.isHidden = false
    }

    private func finishInstallation(status: Int32) {
        cancelEscalation?.cancel()
        cancelEscalation = nil
        cancelKillEscalation?.cancel()
        cancelKillEscalation = nil
        installerProcess = nil
        progress.stopAnimation(nil)
        progress.isHidden = true

        if status == 0 {
            showSuccess()
        } else if cancelRequested {
            showFailure(
                stage: "Easy Install stopped",
                detail: "No unverified version was left active. If Viventium was already installed, its last verified version remains available. Retry when you are ready."
            )
        } else {
            showFailure(
                stage: "Easy Install needs your attention",
                detail: "Viventium was not activated because its checks did not pass. An existing verified installation remains available; a first install remains unactivated. Retry, or download a fresh installer if this continues."
            )
        }
    }

    private func showSuccess() {
        updateStatus(
            stage: "Viventium is ready",
            detail: "Easy Install finished and verified the local app. Open Viventium to connect your preferred account and begin."
        )
        cancelButton.isHidden = true
        secondaryButton.isHidden = false
        primaryButton.isHidden = false
        primaryButton.title = "Open Viventium"
        primaryButton.setAccessibilityLabel("Open Viventium")
        primaryButton.setAccessibilityHelp("Open the local Viventium app in your browser")
        window.makeFirstResponder(primaryButton)
    }

    private func showFailure(stage: String, detail: String) {
        progress.stopAnimation(nil)
        progress.isHidden = true
        updateStatus(stage: stage, detail: detail)
        cancelButton.isHidden = true
        secondaryButton.isHidden = false
        primaryButton.isHidden = false
        primaryButton.title = "Retry"
        primaryButton.setAccessibilityLabel("Retry Easy Install")
        primaryButton.setAccessibilityHelp("Run Easy Install again")
        window.makeFirstResponder(primaryButton)
    }

    @objc private func requestCancel() {
        guard let process = installerProcess, process.isRunning, !cancelRequested else { return }
        cancelRequested = true
        cancelButton.isEnabled = false
        updateStatus(
            stage: "Cancel requested — finishing a safe checkpoint…",
            detail: "Easy Install is stopping its owned installer tasks and will not leave an unverified version active."
        )
        process.interrupt()
        let terminate = DispatchWorkItem { [weak self, weak process] in
            guard let self, let process,
                  self.installerProcess === process,
                  process.isRunning else { return }
            process.terminate()
        }
        cancelEscalation = terminate
        DispatchQueue.global(qos: .userInitiated).asyncAfter(deadline: .now() + 8, execute: terminate)
        let kill = DispatchWorkItem { [weak self, weak process] in
            guard let self, let process,
                  self.installerProcess === process,
                  process.isRunning else { return }
            _ = Darwin.kill(process.processIdentifier, SIGKILL)
        }
        cancelKillEscalation = kill
        DispatchQueue.global(qos: .userInitiated).asyncAfter(deadline: .now() + 15, execute: kill)
    }

    @objc private func performPrimaryAction() {
        if primaryButton.title == "Open Viventium" {
            guard let url = URL(string: "http://127.0.0.1:3190") else { return }
            NSWorkspace.shared.open(url)
            NSApp.terminate(nil)
        } else {
            startInstallation()
        }
    }

    @objc private func quit() {
        NSApp.terminate(nil)
    }
}

private final class BootstrapAppDelegate: NSObject, NSApplicationDelegate {
    private var windowController: BootstrapWindowController?

    func applicationDidFinishLaunching(_ notification: Notification) {
        let controller = BootstrapWindowController()
        windowController = controller
        controller.showAndStart()
    }

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        guard windowController?.requestApplicationTermination() != false else {
            return .terminateCancel
        }
        return .terminateNow
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }
}

let arguments = Array(CommandLine.arguments.dropFirst())
if CommandLine.arguments.dropFirst().isEmpty {
    let application = NSApplication.shared
    let delegate = BootstrapAppDelegate()
    application.setActivationPolicy(.regular)
    application.delegate = delegate
    application.run()
} else {
    exit(runHeadless(arguments: arguments))
}

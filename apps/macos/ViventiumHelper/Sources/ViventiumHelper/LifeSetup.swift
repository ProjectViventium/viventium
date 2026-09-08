import AppKit
import SwiftUI

struct LifeSetupState: Decodable {
    struct Intent: Decodable {
        var text: String
        var folders: [String]?
    }
    var enabled: Bool
    var folder: String?
    var intent: Intent?
}

@MainActor
final class LifeSetupController: ObservableObject {
    typealias Runner = @Sendable ([String], String?) -> (exitStatus: Int32, stdout: String)
    @Published private(set) var state: LifeSetupState?
    @Published private(set) var busy = false
    @Published private(set) var message: String?
    @Published var text = ""
    @Published var folders: [String] = []
    private let run: Runner
    private var window: NSWindow?

    init(run: @escaping Runner) { self.run = run }

    func show() {
        if self.window == nil {
            let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 510, height: 540),
                                  styleMask: [.titled, .closable], backing: .buffered, defer: false)
            window.title = "Life"
            window.isReleasedWhenClosed = false
            window.contentView = NSHostingView(rootView: LifeSetupView(controller: self))
            window.center()
            self.window = window
        }
        self.window?.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        self.perform(["status"])
    }

    func dismiss() { self.window?.orderOut(nil) }

    func setEnabled(_ enabled: Bool) { self.perform([enabled ? "enable" : "disable"]) }

    func save() {
        self.perform(["intent", "--stdin-json"], input: ["text": self.text, "folders": self.folders])
    }

    func clear() { self.perform(["intent", "--clear"]) }

    func chooseFolders() {
        let panel = NSOpenPanel()
        panel.title = "Choose folders you may connect later"
        panel.prompt = "Choose"
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = true
        guard panel.runModal() == .OK else { return }
        for url in panel.urls where !self.folders.contains(url.path) { self.folders.append(url.path) }
    }

    func chooseRoot() {
        let panel = NSOpenPanel()
        panel.title = "Choose where to keep Life"
        panel.prompt = "Choose"
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.canCreateDirectories = true
        guard panel.runModal() == .OK, let url = panel.url else { return }
        self.perform(["enable", "--stdin-json"], input: ["folder": url.path])
    }

    func openFolder() {
        guard let folder = self.state?.folder else { return }
        if !NSWorkspace.shared.open(URL(fileURLWithPath: folder, isDirectory: true)) {
            self.message = "This folder is unavailable. Choose a folder on this Mac."
        }
    }

    private func perform(_ arguments: [String], input: [String: Any]? = nil) {
        guard !self.busy else { return }
        self.busy = true
        self.message = nil
        let encoded = input.flatMap { try? JSONSerialization.data(withJSONObject: $0) }
            .flatMap { String(data: $0, encoding: .utf8) }
        let runner = self.run
        Task.detached(priority: .userInitiated) {
            let result = runner(["life"] + arguments + ["--json", "--show-path"], encoded)
            let data = result.stdout.data(using: .utf8) ?? Data()
            let next = try? JSONDecoder().decode(LifeSetupState.self, from: data)
            let failure = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any]
            await MainActor.run {
                self.busy = false
                guard result.exitStatus == 0, let next else {
                    self.message = failure?["message"] as? String ?? "Life settings could not be saved. Try again."
                    return
                }
                self.state = next
                if arguments.first != "enable" {
                    self.text = next.intent?.text ?? ""
                    self.folders = next.intent?.folders ?? []
                }
                if arguments.first != "status" {
                    switch arguments.first {
                    case "disable": self.message = "Life is off. Your folder and personal notes are kept."
                    case "enable": self.message = "Life is on. Save your intent when ready."
                    default: self.message = "Saved. Nothing has been read or connected."
                    }
                }
            }
        }
    }
}

struct LifeSetupView: View {
    @ObservedObject var controller: LifeSetupController

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Connect your life").font(.title2.weight(.semibold))
            Text("Keep the context you want Viventium to know. For now, this saves your intent only.")
                .foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
            Toggle("Enable Life", isOn: Binding(get: { self.controller.state?.enabled ?? false }, set: self.controller.setEnabled))
            HStack {
                VStack(alignment: .leading, spacing: 3) {
                    Text("Life folder").fontWeight(.medium)
                    Text(self.controller.state?.folder ?? "Loading…").font(.caption).foregroundStyle(.secondary)
                        .lineLimit(2).textSelection(.enabled)
                }
                Spacer()
                Button("Choose…", action: self.controller.chooseRoot)
                Button("Open", action: self.controller.openFolder)
            }
            Divider()
            Text("What would you like to connect?").fontWeight(.medium)
            TextEditor(text: self.$controller.text).font(.body).frame(height: 90)
                .overlay(RoundedRectangle(cornerRadius: 6).stroke(Color.secondary.opacity(0.3)))
                .accessibilityLabel("What to connect")
            if !self.controller.folders.isEmpty {
                ScrollView {
                    VStack(alignment: .leading, spacing: 6) {
                        ForEach(self.controller.folders, id: \.self) { folder in
                            HStack {
                                Image(systemName: "folder")
                                Text(URL(fileURLWithPath: folder).lastPathComponent).lineLimit(1).help(folder)
                                Spacer()
                                Button("Remove") { self.controller.folders.removeAll { $0 == folder } }
                                    .buttonStyle(.borderless).accessibilityLabel("Remove " + URL(fileURLWithPath: folder).lastPathComponent)
                            }
                        }
                    }
                }.frame(height: min(CGFloat(self.controller.folders.count) * 28, 84))
            }
            HStack {
                Button("Choose folders…", action: self.controller.chooseFolders)
                Spacer()
                Button("Clear saved intent", action: self.controller.clear)
            }
            Text("Choosing a folder does not read, upload or index its files, or give Viventium access to them.")
                .font(.callout).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
            if let message = self.controller.message {
                Text(message).font(.callout).fixedSize(horizontal: false, vertical: true)
                    .accessibilityLabel("Life status").accessibilityValue(message)
            }
            HStack {
                Button("Not now", action: self.controller.dismiss)
                Spacer()
                if self.controller.busy { ProgressView().controlSize(.small) }
                Button("Save intent", action: self.controller.save)
                    .buttonStyle(.borderedProminent)
                    .disabled(self.controller.text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && self.controller.folders.isEmpty)
            }
        }.padding(24).frame(width: 490).disabled(self.controller.busy)
    }
}

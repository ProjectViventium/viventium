"""The Mac call shortcut targets the existing loopback authenticated chat, not a new call service."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "apps/macos/ViventiumHelper/Sources/ViventiumHelper/ViventiumHelperApp.swift"


def function(source: str, signature: str) -> str:
    start = source.index(signature)
    first_brace = source.index("{", start)
    depth = 0
    for offset in range(first_brace, len(source)):
        depth += source[offset] == "{"
        depth -= source[offset] == "}"
        if depth == 0:
            return source[start:offset + 1]
    raise AssertionError("Unclosed Swift function")


@pytest.fixture(scope="module")
def call_url_probe(tmp_path_factory):
    directory = tmp_path_factory.mktemp("helper-local-call")
    builder = function(HELPER.read_text(), "private nonisolated static func localCallURL(")
    harness = directory / "call.swift"
    source = HELPER.read_text()
    entry = function(source, "    func openLocalCall()")
    refresh = function(source, "    private func refreshState(force: Bool = false)")
    host_selection = "let host = " + refresh.split("        let host = ", 1)[1].split("        self.openURLString", 1)[0]
    frontend_url = function(source, "private nonisolated static func frontendURLString(")
    harness.write_text('''import Foundation
struct RuntimePorts {
    let frontendPort: Int
    let voiceEnabled: Bool
    let nativeRuntime: Bool
}
enum LocalNetworkAddressResolver {
    static func currentHost() -> String? { "192.0.2.24" }
}
struct Probe {
''' + builder.replace("private nonisolated static", "static", 1) + "\n" + frontend_url.replace("private nonisolated static", "static", 1) + '''
    static func openOrigin(native: Bool, port: Int) -> String {
        let runtime = RuntimePorts(frontendPort: port, voiceEnabled: true, nativeRuntime: native)
''' + host_selection + '''
        return frontendURLString(host: host, port: port)
    }
}
for native in [true, false] {
    print("origin \\(native) \\(Probe.openOrigin(native: native, port: 3190))")
}
for port in [3190, 4420] {
    for enabled in [true, false] {
        for native in [true, false] {
            let value = Probe.localCallURL(runtime: RuntimePorts(frontendPort: port, voiceEnabled: enabled, nativeRuntime: native))
            print("\\(port) \\(enabled) \\(native) \\(value?.absoluteString ?? "unavailable")")
        }
    }
}
struct Config { let appSupportDir = "/synthetic/support" }
struct RuntimeEnvParser {
    func readRuntime(appSupportDir: String) -> RuntimePorts {
        RuntimePorts(frontendPort: 3190, voiceEnabled: true, nativeRuntime: false)
    }
}
enum StackState: String, CaseIterable { case running, needsAttention, starting, stopping, stopped, unavailable }
class EntryProbe {
    var config: Config? = Config()
    let envParser = RuntimeEnvParser()
    var stackState = StackState.running
    var opened = 0
    var started = 0
    static func localCallURL(runtime: RuntimePorts) -> URL? { Probe.localCallURL(runtime: runtime) }
    func openLocalCallBrowser(runtime: RuntimePorts) { opened += 1 }
    func startStack(openWhenReady: Bool, openLocalCallWhenReady: Bool) {
        precondition(openWhenReady && openLocalCallWhenReady)
        started += 1
    }
''' + entry + '''
}
for state in StackState.allCases {
    let probe = EntryProbe()
    probe.stackState = state
    probe.openLocalCall()
    print("entry \\(state.rawValue) \\(probe.opened) \\(probe.started)")
}
''')
    executable = directory / "call"
    compile_result = subprocess.run(["swiftc", str(harness), "-o", str(executable)], capture_output=True, text=True, timeout=60)
    assert compile_result.returncode == 0, compile_result.stderr
    result = subprocess.run([str(executable)], capture_output=True, text=True, check=True, timeout=10)
    return result.stdout.splitlines()


def test_call_shortcut_uses_configured_frontend_loopback_and_one_normal_intent(call_url_probe):
    for line in call_url_probe:
        if line.startswith(("entry ", "origin ")):
            continue
        port, enabled, native, destination = line.split(" ", 3)
        expected = f"http://localhost:{port}/c/new?viventiumCall=1" if enabled == "true" and native == "false" else "unavailable"
        assert destination == expected


def test_menu_and_start_recovery_use_existing_helper_lifecycle():
    source = HELPER.read_text()
    entry = function(source, "    func openLocalCall()")
    assert 'Button("Call on this Mac…") { self.controller.openLocalCall() }' in source
    assert "if self.controller.localCallEnabled" in source
    assert "case .starting, .stopping:" in entry
    assert "self.openLocalCallBrowser(runtime: runtime)" in entry
    assert "self.startStack(openWhenReady: true, openLocalCallWhenReady: true)" in entry
    assert "self.localCallEnabled = runtime.voiceEnabled && !runtime.nativeRuntime" in source
    assert 'voiceEnabled: self.boolValue(values["VIVENTIUM_VOICE_ENABLED"])' in source


def test_call_shortcut_opens_or_starts_once_without_extra_confirmation(call_url_probe):
    expected = {
        "running": (1, 0), "needsAttention": (1, 0),
        "starting": (0, 0), "stopping": (0, 0),
        "stopped": (0, 1), "unavailable": (0, 1),
    }
    actual = {}
    for line in call_url_probe:
        if not line.startswith("entry "):
            continue
        _, state, opened, started = line.split()
        actual[state] = (int(opened), int(started))
    assert actual == expected


def test_shared_helper_open_uses_reachable_local_origin_instead_of_discovered_lan(call_url_probe):
    origins = {}
    for line in call_url_probe:
        if line.startswith("origin "):
            _, native, destination = line.split()
            origins[native] = destination
    assert origins == {"true": "http://127.0.0.1:3190", "false": "http://localhost:3190"}

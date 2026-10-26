"""Run the owning helper reconciler against settled dependency and process-loss facts."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "apps/macos/ViventiumHelper/Sources/ViventiumHelper/ViventiumHelperApp.swift"


@pytest.fixture(scope="module")
def reconcile_probe(tmp_path_factory):
    directory = tmp_path_factory.mktemp("dependency-reconcile")
    source = HELPER.read_text()
    policy = "enum RuntimeDesiredState:" + source.split("enum RuntimeDesiredState:", 1)[1].split(
        "private struct HelperConfig:", 1,
    )[0]
    # Count entry into the real policy methods without changing their decisions.
    for name in ("recordLaunchAttempt", "recordUnhealthy", "recordHealthy"):
        start = policy.index("mutating func " + name + "(")
        brace = policy.index("{", start)
        policy = policy[:brace + 1] + f"\n        Calls.{name} += 1" + policy[brace + 1:]
    snapshot = "private struct StackHealthSnapshot" + source.split("private struct StackHealthSnapshot", 1)[1].split(
        "private struct HealWorkflowSettings", 1,
    )[0]
    reconcile = "    private func reconcileRuntimeSupervision(trigger:" + source.split(
        "    private func reconcileRuntimeSupervision(trigger:", 1,
    )[1].split("    private func setRuntimeDesiredState(", 1)[0]
    harness = directory / "reconcile.swift"
    harness.write_text("import Foundation\n" + r'''
private enum Calls {
    static var recordLaunchAttempt = 0
    static var recordUnhealthy = 0
    static var recordHealthy = 0
    static var startStack = 0
}
''' + policy + snapshot + r'''
private struct Config {
    let repoRoot = "/synthetic/repository"
    let appSupportDir = "/synthetic/support"
}
private struct RuntimePorts {}
private struct RuntimeEnvParser {
    func readRuntime(appSupportDir: String) -> RuntimePorts { RuntimePorts() }
}
private enum StackState: Equatable {
    case running, needsAttention, unavailable(String)
    var actionBusy: Bool { false }
}
@MainActor private final class HelperController {
    var config: Config? = Config()
    var runtimeSupervision = RuntimeSupervisionState.defaultRunning
    var runtimeSupervisionCheckInFlight = false
    var stackLaunchInProgress = false
    var stackState = StackState.running
    var runtimeSupervisionStableHealthSeconds: TimeInterval = 0
    var runtimeSupervisionBaseDelaySeconds: TimeInterval = 15
    var runtimeSupervisionMaximumDelaySeconds: TimeInterval = 900
    var persistenceCalls = 0
    var snapshot: StackHealthSnapshot

    init(snapshot: StackHealthSnapshot) { self.snapshot = snapshot }
    func refreshRuntimeDesiredState() {}
    func stackHealthSnapshot(runtime: RuntimePorts) async -> StackHealthSnapshot { self.snapshot }
    func persistRuntimeSupervision() -> Bool { self.persistenceCalls += 1; return true }
    func log(_ value: String) {}
    func startStack(openWhenReady: Bool, launchReason: String,
                    recordsDesiredRunning: Bool, supervisedLaunch: Bool) {
        Calls.startStack += 1
    }
    static func stackOwnedByDifferentRepo(runtime: RuntimePorts, appSupportDir: String,
                                         expectedRepoRoot: String,
                                         knownSnapshot: StackHealthSnapshot?) async -> Bool { false }
    static func cliOperationStillRunning(appSupportDir: String) -> Bool { false }
    static func inFlightStackState(appSupportDir: String, repoRoot: String) -> String? { nil }
    static func telegramRecoveryPointerExists(appSupportDir: String) -> Bool { false }
    static func telegramRecoveryWasRunning(appSupportDir: String) -> Bool? { nil }

''' + reconcile + r'''
    func runReconcile() async throws {
        self.reconcileRuntimeSupervision(trigger: "synthetic-observation")
        for _ in 0..<1000 {
            if !self.runtimeSupervisionCheckInFlight { return }
            try await Task.sleep(nanoseconds: 1_000_000)
        }
        preconditionFailure("Reconciler did not settle")
    }
}
@main struct ReconcileProbe {
    @MainActor static func main() async throws {
        let mode = CommandLine.arguments[1]
        let allLocalRunning = mode != "missing-local"
        let failed = StackHealthSnapshot(apiReady: true, frontendReady: true,
            playgroundReady: false, requiresPlayground: false, optionalSurfacesReady: false,
            allLocalServicesRunning: allLocalRunning)
        let controller = HelperController(snapshot: failed)
        if mode != "missing-local" {
            controller.runtimeSupervision.consecutiveLaunchAttempts = 2
            controller.runtimeSupervision.nextLaunchAttemptAt = Date(timeIntervalSinceNow: -60)
            controller.runtimeSupervision.healthySince = Date(timeIntervalSinceNow: -600)
        }
        let before = controller.runtimeSupervision
        try await controller.runReconcile()
        let attentionHeld = controller.stackState == .needsAttention
        let statePreserved = controller.runtimeSupervision == before
        let firstLaunches = Calls.startStack
        let firstAttempts = Calls.recordLaunchAttempt
        let firstUnhealthy = Calls.recordUnhealthy
        if mode == "recovered" {
            controller.snapshot = StackHealthSnapshot(apiReady: true, frontendReady: true,
                playgroundReady: false, requiresPlayground: false, optionalSurfacesReady: true,
                allLocalServicesRunning: true)
            try await controller.runReconcile()
        }
        let result: [String: Any] = ["attentionHeld": attentionHeld,
            "statePreserved": statePreserved, "firstLaunches": firstLaunches,
            "firstAttempts": firstAttempts, "firstUnhealthy": firstUnhealthy,
            "launches": Calls.startStack, "attempts": Calls.recordLaunchAttempt,
            "unhealthy": Calls.recordUnhealthy, "healthy": Calls.recordHealthy,
            "uiRunning": controller.stackState == .running,
            "backoffCleared": controller.runtimeSupervision.consecutiveLaunchAttempts == 0 &&
                controller.runtimeSupervision.nextLaunchAttemptAt == nil]
        print(String(data: try JSONSerialization.data(withJSONObject: result), encoding: .utf8)!)
    }
}
''')
    executable = directory / "reconcile"
    build = subprocess.run(["xcrun", "swiftc", "-parse-as-library", str(harness), "-o", str(executable)],
                           capture_output=True, text=True, timeout=60)
    assert build.returncode == 0, build.stderr

    def run(mode: str):
        result = subprocess.run([str(executable), mode], capture_output=True, text=True, timeout=5)
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)

    return run


def test_settled_dependency_attention_does_not_schedule_or_start_a_runtime(reconcile_probe) -> None:
    result = reconcile_probe("dependency-down")
    assert result["attentionHeld"] and result["statePreserved"]
    assert result["firstAttempts"] == result["firstLaunches"] == result["firstUnhealthy"] == 0


def test_missing_local_service_retains_the_existing_recovery_path(reconcile_probe) -> None:
    result = reconcile_probe("missing-local")
    assert result["attentionHeld"]
    assert result["firstAttempts"] == result["firstLaunches"] == result["firstUnhealthy"] == 1
    assert not result["statePreserved"]


def test_dependency_recovery_clears_attention_and_existing_backoff_without_a_launch(reconcile_probe) -> None:
    result = reconcile_probe("recovered")
    assert result["attentionHeld"] and result["statePreserved"]
    assert result["uiRunning"] and result["backoffCleared"]
    assert result["healthy"] == 1
    assert result["attempts"] == result["launches"] == result["unhealthy"] == 0

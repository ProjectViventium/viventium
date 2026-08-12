from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER_SOURCE = (
    REPO_ROOT
    / "apps"
    / "macos"
    / "ViventiumHelper"
    / "Sources"
    / "ViventiumHelper"
    / "ViventiumHelperApp.swift"
)
HELPER_INSTALLER = REPO_ROOT / "scripts" / "viventium" / "install_macos_helper.sh"


def test_runtime_supervision_policy_honors_stop_and_bounds_retry_backoff(
    tmp_path: Path,
) -> None:
    source = HELPER_SOURCE.read_text(encoding="utf-8")
    policy = source.split("enum RuntimeDesiredState:", 1)[1].split(
        "private struct HelperConfig:",
        1,
    )[0]
    policy = "enum RuntimeDesiredState:" + policy
    harness = tmp_path / "RuntimeSupervisionPolicyHarness.swift"
    executable = tmp_path / "runtime-supervision-policy"
    harness.write_text(
        """
import Foundation

__POLICY__

@main
struct RuntimeSupervisionPolicyHarness {
    static func main() throws {
        let startedAt = Date(timeIntervalSince1970: 1_000)
        var state = RuntimeSupervisionState.defaultRunning
        precondition(state.shouldLaunch(at: startedAt))

        state.recordLaunchAttempt(at: startedAt, baseDelay: 15, maximumDelay: 900)
        precondition(!state.shouldLaunch(at: startedAt.addingTimeInterval(14)))
        precondition(state.shouldLaunch(at: startedAt.addingTimeInterval(15)))

        state.recordLaunchAttempt(
            at: startedAt.addingTimeInterval(15),
            baseDelay: 15,
            maximumDelay: 900
        )
        precondition(!state.shouldLaunch(at: startedAt.addingTimeInterval(44)))
        precondition(state.shouldLaunch(at: startedAt.addingTimeInterval(45)))

        for offset in 0..<20 {
            state.recordLaunchAttempt(
                at: startedAt.addingTimeInterval(TimeInterval(100 + offset)),
                baseDelay: 15,
                maximumDelay: 900
            )
        }
        precondition(
            state.nextLaunchAttemptAt == startedAt.addingTimeInterval(119 + 900)
        )

        state.requestStopped()
        precondition(!state.shouldLaunch(at: .distantFuture))
        let encoded = try JSONEncoder().encode(state)
        let decoded = try JSONDecoder().decode(RuntimeSupervisionState.self, from: encoded)
        precondition(decoded == state)
        precondition(decoded.schemaVersion == 1)
        precondition(decoded.desiredState == .stopped)

        state.requestRunning()
        precondition(state.shouldLaunch(at: startedAt))
        precondition(state.consecutiveLaunchAttempts == 0)
        precondition(state.nextLaunchAttemptAt == nil)

        state.recordLaunchAttempt(at: startedAt, baseDelay: 15, maximumDelay: 900)
        state.recordHealthy(at: startedAt, stabilityWindow: 300)
        state.recordUnhealthy(
            at: startedAt.addingTimeInterval(5),
            stabilityWindow: 300,
            baseDelay: 15,
            maximumDelay: 900
        )
        precondition(
            state.nextLaunchAttemptAt == startedAt.addingTimeInterval(5 + 15)
        )
        state.recordHealthy(at: startedAt.addingTimeInterval(20), stabilityWindow: 300)
        state.recordHealthy(at: startedAt.addingTimeInterval(320), stabilityWindow: 300)
        precondition(state.desiredState == .running)
        precondition(state.consecutiveLaunchAttempts == 0)
        precondition(state.nextLaunchAttemptAt == nil)
        print("runtime-supervision-policy-ok")
    }
}
""".replace("__POLICY__", policy),
        encoding="utf-8",
    )

    sdk_path = subprocess.run(
        ["xcrun", "--show-sdk-path"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    subprocess.run(
        [
            "xcrun",
            "swiftc",
            "-parse-as-library",
            "-sdk",
            sdk_path,
            str(harness),
            "-o",
            str(executable),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    completed = subprocess.run(
        [str(executable)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stdout.strip() == "runtime-supervision-policy-ok"


def test_helper_config_supervision_save_preserves_unknown_future_fields(
    tmp_path: Path,
) -> None:
    source = HELPER_SOURCE.read_text(encoding="utf-8")
    persistence = source.split("enum RuntimeDesiredState:", 1)[1].split(
        "private struct ActiveRuntimeCheckout:",
        1,
    )[0]
    persistence = "enum RuntimeDesiredState:" + persistence
    harness = tmp_path / "HelperConfigPersistenceHarness.swift"
    executable = tmp_path / "helper-config-persistence"
    config_path = tmp_path / "helper-config.json"
    harness.write_text(
        r'''
import Foundation

__PERSISTENCE__

@main
struct HelperConfigPersistenceHarness {
    static func main() throws {
        let existing = Data(
            """
            {
              "repoRoot": "/public/viventium",
              "appSupportDir": "/private/viventium",
              "showInStatusBar": false,
              "allowProtectedRepoRoot": true,
              "futureTopLevel": {"enabled": true, "nested": {"keep": "yes"}},
              "runtimeSupervision": {
                "schemaVersion": 1,
                "desiredState": "running",
                "consecutiveLaunchAttempts": 3,
                "nextLaunchAttemptAt": null,
                "healthySince": null,
                "futureNestedPolicy": {"mode": "careful"}
              }
            }
            """.utf8
        )
        let configURL = URL(fileURLWithPath: CommandLine.arguments[1])
        try existing.write(to: configURL, options: .atomic)
        var config = try JSONDecoder().decode(HelperConfig.self, from: existing)
        var supervision = config.runtimeSupervision!
        supervision.requestStopped()
        config.runtimeSupervision = supervision

        try HelperConfigPreservingStore.save(config: config, to: configURL)
        let encoded = try Data(contentsOf: configURL)
        let object = try JSONSerialization.jsonObject(with: encoded) as! [String: Any]
        precondition((object["showInStatusBar"] as? Bool) == false)
        precondition((object["allowProtectedRepoRoot"] as? Bool) == true)
        let future = object["futureTopLevel"] as! [String: Any]
        precondition((future["enabled"] as? Bool) == true)
        precondition(
            ((future["nested"] as! [String: Any])["keep"] as? String) == "yes"
        )
        let persistedSupervision = object["runtimeSupervision"] as! [String: Any]
        precondition(
            (persistedSupervision["desiredState"] as? String) == "stopped"
        )
        precondition(
            ((persistedSupervision["futureNestedPolicy"] as! [String: Any])["mode"]
                as? String) == "careful"
        )
        print("helper-config-passthrough-ok")
    }
}
'''.replace("__PERSISTENCE__", persistence),
        encoding="utf-8",
    )

    sdk_path = subprocess.run(
        ["xcrun", "--show-sdk-path"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    subprocess.run(
        [
            "xcrun",
            "swiftc",
            "-parse-as-library",
            "-sdk",
            sdk_path,
            str(harness),
            "-o",
            str(executable),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    completed = subprocess.run(
        [str(executable), str(config_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stdout.strip() == "helper-config-passthrough-ok"
    assert config_path.stat().st_mode & 0o777 == 0o600


def test_helper_reconciles_running_intent_after_launch_window_and_persists_stop() -> None:
    source = HELPER_SOURCE.read_text(encoding="utf-8")
    lifecycle = source.split("private func activateHelperLifecycle()", 1)[1].split(
        "private func presentStatusBarRestorePrompt",
        1,
    )[0]
    start = source.split("private func startStack(", 1)[1].split(
        "private func stopStack(",
        1,
    )[0]
    stop = source.split("private func stopStack(", 1)[1].split(
        "private func cancelDelayedQuitWatch",
        1,
    )[0]
    supervision = source.split("private func reconcileRuntimeSupervision(", 1)[1].split(
        "private func log(",
        1,
    )[0]

    assert "didAttemptLaunchAutostart" not in source
    assert "autoStartRetryWindowSeconds" not in source
    assert 'self?.reconcileRuntimeSupervision(trigger: "poll")' in lifecycle
    assert 'self?.reconcileRuntimeSupervision(trigger: "launch")' in lifecycle
    assert "runtimeSupervision: RuntimeSupervisionState?" in source
    assert "setRuntimeDesiredState(.running)" in start
    assert "setRuntimeDesiredState(.stopped)" in stop
    assert "guard self.runtimeSupervision.desiredState == .running" in supervision
    assert "self.runtimeSupervision.recordHealthy(" in supervision
    assert "self.runtimeSupervision.recordLaunchAttempt(" in supervision
    assert "self.persistRuntimeSupervision()" in supervision
    assert 'launchReason: "supervisor:\\(trigger)"' in supervision


def test_helper_supervision_repairs_configured_sidecars_including_scheduling() -> None:
    source = HELPER_SOURCE.read_text(encoding="utf-8")
    refresh_state = source.split("private func refreshState(", 1)[1].split(
        "private func stackHealthSnapshot(",
        1,
    )[0]
    supervision = source.split("private func reconcileRuntimeSupervision(", 1)[1].split(
        "private func log(",
        1,
    )[0]
    optional_health = source.split(
        "private nonisolated static func optionalSurfacesReady(",
        1,
    )[1].split(
        "private nonisolated static func frontendURLString(",
        1,
    )[0]

    assert 'values["START_SCHEDULING_MCP"]' in source
    assert 'self.rebasedURL(values["SCHEDULING_MCP_URL"], path: "/health")' in source
    assert "return await self.managedServicesHealthy(runtime: runtime)" in optional_health
    assert (
        "if snapshot.needsAttention {\n"
        "                self.stackState = .needsAttention\n"
        "                return\n"
        "            }"
    ) in refresh_state
    assert (
        "if snapshot.needsAttention {\n"
        "                self.stackState = .needsAttention\n"
        "            }"
    ) in supervision
    assert "self.startStack(" in supervision


def test_helper_refresh_and_checkout_rebinding_preserve_supervision_state() -> None:
    source = HELPER_SOURCE.read_text(encoding="utf-8")
    installer = HELPER_INSTALLER.read_text(encoding="utf-8")
    write_config = installer.split("write_helper_config() {", 1)[1].split(
        "write_helper_launcher_scripts()",
        1,
    )[0]

    assert source.count("runtimeSupervision: config.runtimeSupervision") == 3
    assert "config = dict(existing)" in write_config
    assert '"runtimeSupervision"' not in write_config


def test_supervision_shares_in_flight_health_probe_with_status_refresh() -> None:
    source = HELPER_SOURCE.read_text(encoding="utf-8")
    snapshot = source.split(
        "private func stackHealthSnapshot(runtime: RuntimePorts, force: Bool = false)",
        1,
    )[1].split("private func refreshLaunchAtLoginState", 1)[0]

    assert "private var steadyStateHealthSnapshotTask:" in source
    assert "if let inFlight = self.steadyStateHealthSnapshotTask" in snapshot
    assert "return await inFlight.task.value" in snapshot
    assert "self.steadyStateHealthSnapshotTask = (runtime, task)" in snapshot

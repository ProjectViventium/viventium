#!/usr/bin/env python3
"""Derive installed catalog acceptance from exact, live producer evidence."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import importlib.util
import io
import json
import os
import pwd
import re
import secrets
import stat
import struct
import sys
import wave
import zlib
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
from typing import NoReturn


CONTRACT_VERSION = 1
MANIFEST_SCHEMA = "viventium.installed-catalog-evidence.v1"
VERIFIER_ID = "viventium-installed-catalog-v1"
SOURCE_SIGNATURE_NAMESPACE = "viventium-qa-catalog-source-v1"
REGISTRATION_PATH = Path("qa/parallel-orchestrator/scripts/catalog_case_semantic_verifier.py")
MAX_RESULT_AGE = timedelta(hours=24)
MAX_FUTURE_SKEW = timedelta(seconds=60)
MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024
MAX_EVIDENCE_FILES = 128
MAX_CAPTURE_PIXELS = 25_000_000
MAX_SOURCE_RECEIPTS = 2_048
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
SHA256_REF = re.compile(r"sha256:[0-9a-f]{64}\Z")
SESSION_REF = re.compile(r"qa_[0-9a-f]{24}\Z")
SAFE_COMPONENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
MANIFEST_FIELDS = frozenset(
    {
        "candidate",
        "caseId",
        "checks",
        "contractVersion",
        "correlation",
        "environment",
        "evidence",
        "runAt",
        "schema",
    }
)
EVIDENCE_FIELDS = frozenset({"id", "kind", "path", "sha256"})
DOCUMENT_FIELDS = frozenset(
    {
        "artifactDigest",
        "candidateDigest",
        "caseId",
        "contractVersion",
        "kind",
        "observedAt",
        "originSurface",
        "ownerRefHash",
        "payload",
        "producerId",
        "serviceId",
        "sessionRef",
        "sourceReceipt",
    }
)
SOURCE_RECEIPT_FIELDS = frozenset(
    {
        "artifactDigest",
        "candidateDigest",
        "caseId",
        "contractVersion",
        "observedAt",
        "ownerRefHash",
        "payloadSha256",
        "processIdentity",
        "processStartMarker",
        "producerId",
        "sequence",
        "serviceId",
        "sessionRef",
        "signature",
        "signerId",
        "signerIdentity",
        "sourceRefHash",
        "surface",
        "verifierId",
    }
)
PROCESS_FIELDS = frozenset({"pid", "startedAt", "startMarker", "executableSha256"})
OBSERVATION_FIELDS = frozenset(
    {"observationId", "ownerRefHash", "recordedAt", "sourceRefHash", "facts"}
)
SURFACES = frozenset({"api", "cli", "installer", "scheduler", "telegram", "voice", "web", "workbench"})
CAPTURE_SURFACES = frozenset({"telegram", "voice", "web"})
_DERIVED_PASS = object()
_DERIVATION_KEY = secrets.token_bytes(32)
_ISSUED_PASSES: dict[int, tuple[dict[str, object], str, str]] = {}


@dataclass(frozen=True)
class ProducerSpec:
    producer_id: str
    service_id: str


@dataclass(frozen=True)
class Requirement:
    id: str
    kind: str
    facts: tuple[tuple[str, object], ...]


@dataclass(frozen=True)
class CaseSpec:
    surface: str
    capture_surfaces: frozenset[str]
    requirements: tuple[Requirement, ...]
    restart_required: bool = False


@dataclass
class LiveAuthority:
    candidate_digest: str
    artifact_digest: str
    owner_ref_hash: str
    case_id: str
    session_ref: str
    session_started_at: datetime
    session_expires_at: datetime
    producer_processes: Mapping[str, Mapping[str, object]]
    producer_receipts: Mapping[str, Mapping[str, object]]
    source_signature_verifier: Callable[[Mapping[str, object], ProducerSpec], None]


EVIDENCE_PRODUCERS = {
    "account_ledger": ProducerSpec("core.account_preference_ledger", "librechat-core"),
    "action_ledger": ProducerSpec("glasshive.exact_action_ledger", "glasshive-runtime"),
    "artifact_ledger": ProducerSpec("glasshive.artifact_delivery_ledger", "glasshive-runtime"),
    "authorization_ledger": ProducerSpec("core.owner_authorization_ledger", "librechat-core"),
    "capability_ledger": ProducerSpec("core.scoped_capability_ledger", "librechat-core"),
    "capacity_ledger": ProducerSpec("glasshive.capacity_reservation_ledger", "glasshive-runtime"),
    "component_identity": ProducerSpec("runtime.component_identity_probe", "runtime-owner"),
    "delivery_ledger": ProducerSpec("core.terminal_delivery_ledger", "librechat-core"),
    "fault_ledger": ProducerSpec("glasshive.typed_fault_ledger", "glasshive-runtime"),
    "installed_identity": ProducerSpec("runtime.installed_artifact_identity", "runtime-owner"),
    "lifecycle_ledger": ProducerSpec("glasshive.immutable_lifecycle_ledger", "glasshive-runtime"),
    "native_runtime_ledger": ProducerSpec("glasshive.native_runtime_ledger", "glasshive-runtime"),
    "network_ledger": ProducerSpec("core.network_and_timing_ledger", "librechat-core"),
    "prompt_ledger": ProducerSpec("core.prompt_snapshot_ledger", "librechat-core"),
    "provider_ledger": ProducerSpec("glasshive.provider_health_ledger", "glasshive-runtime"),
    "quality_scorecard": ProducerSpec("core.exact_model_quality_scorecard", "librechat-core"),
    "release_snapshot": ProducerSpec("runtime.release_evaluator_snapshot", "runtime-owner"),
    "repository_scan": ProducerSpec("runtime.public_boundary_scan", "runtime-owner"),
    "restart_ledger": ProducerSpec("core.exact_restart_recovery_ledger", "librechat-core"),
    "scheduler_ledger": ProducerSpec("glasshive.durable_schedule_ledger", "glasshive-runtime"),
    "security_probe": ProducerSpec("glasshive.owner_isolation_probe", "glasshive-runtime"),
    "telegram_observation": ProducerSpec("telegram.installed_desktop_capture", "telegram-bot"),
    "trace_ledger": ProducerSpec("glasshive.owner_scoped_immutable_trace", "glasshive-runtime"),
    "turn_ledger": ProducerSpec("core.logical_turn_ledger", "librechat-core"),
    "voice_observation": ProducerSpec("core.audible_voice_observation", "librechat-core"),
    "web_observation": ProducerSpec("core.headed_browser_observation", "librechat-core"),
}


def _requirement(check_id: str, kind: str, **facts: object) -> Requirement:
    if not facts or kind not in EVIDENCE_PRODUCERS:
        raise ValueError("catalog requirement has no authoritative producer or typed measurement")
    return Requirement(check_id, kind, tuple(sorted(facts.items())))


def _case(
    surface: str,
    captures: Iterable[str],
    *requirements: Requirement,
    restart: bool = False,
) -> CaseSpec:
    capture_set = frozenset(captures)
    if surface not in SURFACES or not capture_set <= CAPTURE_SURFACES or not requirements:
        raise ValueError("catalog case has no executable evidence requirements")
    identifiers = [requirement.id for requirement in requirements]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("catalog case repeats a semantic requirement")
    return CaseSpec(surface, capture_set, tuple(requirements), restart)


r = _requirement
CASE_SPECS: dict[str, CaseSpec] = {
    "PWK-001": _case("telegram", ("telegram", "web"),
        r("linked-toggle-persists-account-wide", "account_ledger", linkedToggleCount=2, ownerCount=1),
        r("unlinked-user-receives-safe-link", "authorization_ledger", safeLinkCount=1, unauthorizedLaunchCount=0),
        r("toggle-does-not-call-model", "provider_ledger", modelCallCount=0),
        r("web-reload-matches-telegram-preference", "account_ledger", matchingSurfaceCount=2), restart=True),
    "PWK-002": _case("telegram", ("telegram", "web"),
        r("three-source-turns-accounted-once", "turn_ledger", sourceTurnCount=3, duplicateTurnCount=0),
        r("two-independent-workers-created-once", "lifecycle_ledger", distinctWorkCount=2, duplicateWorkCount=0),
        r("main-answers-quick-turn-during-work", "turn_ledger", quickAnswerCount=1, competingAnswerCount=0)),
    "PWK-003": _case("telegram", ("telegram", "web"),
        r("duplicate-ingress-creates-one-work", "lifecycle_ledger", distinctWorkCount=1, replayCount=2),
        r("precommit-disconnect-creates-no-work", "lifecycle_ledger", precommitWorkCount=0),
        r("postcommit-retry-restores-exact-work", "action_ledger", recoveredWorkCount=1, duplicateEffectCount=0),
        r("replay-emits-no-duplicate-callback", "delivery_ledger", duplicateCallbackCount=0)),
    "PWK-004": _case("web", ("web", "telegram"),
        r("active-work-distinguishes-all-states", "account_ledger", distinctVisibleStateCount=8),
        r("retained-terminal-work-remains-visible", "lifecycle_ledger", retainedTerminalCount=1),
        r("active-work-never-exposes-internals", "security_probe", leakedPrivateFieldCount=0)),
    "PWK-005": _case("web", ("web", "telegram", "voice"),
        r("all-exact-worker-actions-are-covered", "action_ledger", distinctActionCount=9, siblingMutationCount=0),
        r("stop-awaits-proven-process-exit", "native_runtime_ledger", confirmedStopCount=1, falseTerminalCount=0),
        r("retry-preserves-exact-workspace", "artifact_ledger", workspaceIdentityCount=1),
        r("terminal-races-never-resurrect-work", "lifecycle_ledger", coveredRaceCount=4, resurrectedWorkCount=0)),
    "PWK-006": _case("web", ("web",),
        r("three-workers-hold-independent-leases", "capacity_ledger", concurrentLeaseCount=3),
        r("fourth-overflow-is-not-accepted", "capacity_ledger", rejectedOverflowCount=1, overflowWorkCount=0),
        r("queued-loss-of-capacity-keeps-deadline", "lifecycle_ledger", boundedQueuedCount=1, falseRunningCount=0)),
    "PWK-007": _case("web", ("web", "telegram"),
        r("exact-process-start-guards-stop", "native_runtime_ledger", verifiedProcessGenerationCount=1, reusedPidKillCount=0),
        r("unconfirmed-stop-stays-nonterminal", "action_ledger", unconfirmedStopCount=1, falseTerminalCount=0),
        r("restart-preserves-exact-mission", "lifecycle_ledger", recoveredWorkCount=1, terminalRegressionCount=0), restart=True),
    "PWK-008": _case("web", ("web", "telegram"),
        r("cross-owner-read-and-control-fail-closed", "authorization_ledger", deniedCrossOwnerOperationCount=4, leakedWorkCount=0),
        r("cross-owner-callback-never-delivers", "delivery_ledger", crossOwnerDeliveryCount=0),
        r("local-and-enterprise-owner-boundaries-match", "security_probe", isolatedDeploymentModeCount=2)),
    "PWK-009": _case("web", ("web", "telegram"),
        r("codex-session-persists-before-completion", "native_runtime_ledger", precompletionSessionCount=1),
        r("real-codex-child-projects-once", "native_runtime_ledger", projectedChildCount=1, duplicateChildCount=0),
        r("recursive-codex-stop-leaves-no-orphan", "action_ledger", orphanProcessCount=0)),
    "PWK-010": _case("web", ("web", "telegram"),
        r("claude-capability-matches-real-child", "native_runtime_ledger", provenChildCount=1, inventedCapabilityCount=0),
        r("claude-session-scope-excludes-unrelated-work", "authorization_ledger", unrelatedSessionExposureCount=0),
        r("native-message-and-stop-remain-worker-local", "action_ledger", workerLocalActionCount=2), restart=True),
    "PWK-011": _case("web", ("web", "telegram", "voice"),
        r("exact-input-bytes-order-and-owner-match", "capability_ledger", validatedInputFamilyCount=7, crossOwnerInputCount=0),
        r("worker-retains-memory-tools-and-connections", "capability_ledger", authorizedCapabilityFamilyCount=6, missingRequiredCapabilityCount=0),
        r("fallback-and-controls-preserve-scope", "provider_ledger", checkedExecutionBoundaryCount=4, authorityExpansionCount=0),
        r("generated-artifacts-arrive-once", "artifact_ledger", deliveredArtifactCount=2, duplicateArtifactCount=0),
        r("sibling-chat-and-credentials-never-leak", "security_probe", leakedSiblingRecordCount=0, leakedCredentialCount=0), restart=True),
    "PWK-012": _case("web", ("web", "telegram"),
        r("broker-grant-begins-only-at-admission", "authorization_ledger", preAdmissionGrantCount=0, admittedGrantCount=1),
        r("unchanged-scope-revalidation-succeeds", "authorization_ledger", unchangedScopeResumeCount=1),
        r("revocation-approval-and-expiry-need-input", "authorization_ledger", distinctRecoverableDenialCount=3)),
    "PWK-013": _case("telegram", ("telegram", "web", "voice"),
        r("callback-fans-out-to-every-destination-once", "delivery_ledger", destinationCount=3, duplicateDeliveryCount=0),
        r("zero-target-callback-raises-attention", "delivery_ledger", zeroTargetAlertCount=1),
        r("only-main-authors-useful-completion", "turn_ledger", mainAuthoredCompletionCount=1, workerAuthoredReplyCount=0)),
    "PWK-014": _case("scheduler", ("web",),
        r("required-work-waits-without-scheduler-lease", "scheduler_ledger", waitingExternalCount=1, waitingLeaseCount=0),
        r("schedule-completes-only-after-every-worker", "scheduler_ledger", requiredTerminalWorkCount=2, prematureCompletionCount=0),
        r("replayed-callback-has-one-schedule-effect", "delivery_ledger", duplicateScheduleCompletionCount=0)),
    "PWK-015": _case("telegram", ("telegram",),
        r("provisional-failure-is-replaced-on-recovery", "delivery_ledger", recoveredResultCount=1, provisionalResidueCount=0),
        r("retry-exhaustion-produces-one-terminal-error", "delivery_ledger", terminalFailureCount=1, duplicateTerminalCount=0)),
    "PWK-016": _case("web", ("web", "telegram"),
        r("focused-turn-makes-no-provider-network-call", "network_ledger", glasshiveRequestCount=0, modelCallCount=0),
        r("focused-local-overhead-meets-budget", "network_ledger", maximumOverheadMs=25),
        r("snapshot-and-admission-timing-are-measured", "network_ledger", measuredPercentileCount=2)),
    "PWK-017": _case("voice", ("voice", "web", "telegram"),
        r("audible-call-controls-exact-worker", "action_ledger", distinctVoiceActionCount=9, siblingMutationCount=0),
        r("speech-revises-main-without-cancelling-work", "turn_ledger", finalSpokenReplyCount=1, cancelledAcceptedWorkCount=0),
        r("voice-hangup-preserves-worker-artifacts", "artifact_ledger", linkedArtifactCount=2, lostAfterHangupCount=0),
        r("wing-and-listen-only-enforce-authority", "authorization_ledger", deniedPassiveLaunchCount=2, unsolicitedCallCount=0)),
    "PWK-018": _case("installer", ("web", "telegram", "voice"),
        r("source-component-pin-build-and-runtime-agree", "component_identity", alignedIdentityLayerCount=5, mismatchedIdentityCount=0),
        r("clean-install-keeps-feature-dark-by-default", "release_snapshot", defaultParallelAvailability=False, defaultMode="focused"),
        r("installed-artifacts-contain-no-private-data", "repository_scan", privateFindingCount=0), restart=True),
    "PWK-019": _case("telegram", ("telegram", "web"),
        r("main-claims-work-only-after-provider-receipt", "turn_ledger", verifiedLaunchReceiptCount=1, prematureClaimCount=0),
        r("conversation-lane-can-control-top-level-work", "action_ledger", authorizedConversationActionCount=2),
        r("mission-root-cannot-create-peer-work", "security_probe", deniedPeerCreationCount=1, createdPeerCount=0)),
    "PWK-020": _case("telegram", ("telegram", "web"),
        r("lost-action-response-reuses-exact-operation", "action_ledger", stableOperationIdentityCount=1, duplicateActionCount=0),
        r("post-effect-crash-recovers-same-receipt", "action_ledger", recoveredReceiptCount=1, pendingForeverCount=0), restart=True),
    "PWK-021": _case("web", ("web", "voice"),
        r("worker-fields-remain-untrusted-structured-data", "prompt_ledger", escapedUntrustedFieldCount=4),
        r("worker-content-never-gains-instruction-authority", "security_probe", promotedInstructionCount=0)),
    "PWK-022": _case("api", ("web", "telegram"),
        r("all-account-and-legacy-routes-enforce-owner", "authorization_ledger", verifiedRouteFamilyCount=3, crossOwnerSuccessCount=0),
        r("model-supplied-owner-never-overrides-trust", "authorization_ledger", rejectedOwnerOverrideCount=1),
        r("owner-denials-have-uniform-safe-shape", "security_probe", leakedExistenceCount=0)),
    "PWK-023": _case("web", ("web", "telegram"),
        r("follow-up-runs-remain-one-work-lifecycle", "lifecycle_ledger", workIdentityCount=1, activeSiblingRunCount=1),
        r("intermediate-completion-cannot-terminalize-work", "delivery_ledger", prematureTerminalDeliveryCount=0),
        r("work-wide-stop-affects-only-exact-mission", "action_ledger", stoppedWorkCount=1, crossWorkMutationCount=0)),
    "PWK-024": _case("web", ("web", "telegram"),
        r("capacity-probe-failures-stay-typed-and-queued", "capacity_ledger", distinctUnavailableProbeCount=4, fabricatedHeadroomCount=0),
        r("measurement-recovery-admits-same-work", "lifecycle_ledger", recoveredWorkCount=1, retryExhaustionCount=0),
        r("recovered-work-produces-exact-artifact", "artifact_ledger", verifiedArtifactCount=1)),
    "PWK-025": _case("api", ("web",),
        r("automatic-workers-run-inside-real-boundary", "security_probe", isolatedWorkerCount=1, hostModeLaunchCount=0),
        r("worker-cannot-read-host-peer-or-state", "security_probe", deniedProtectedSurfaceCount=5, leakedSecretCount=0),
        r("unsafe-existing-host-work-disables-admission", "release_snapshot", effectiveAvailability=False, cancelledExistingWorkCount=0),
        r("isolated-worker-retains-authorized-tools-and-caps", "capability_ledger", authorizedToolCount=1, capBypassCount=0)),
    "PWK-026": _case("web", ("web",),
        r("clean-seed-creates-one-orchestration-declaration", "component_identity", seededDeclarationCount=1),
        r("reseed-preserves-agent-owned-declaration", "component_identity", overwrittenDeclarationCount=0, duplicatedDeclarationCount=0), restart=True),
    "PWK-027": _case("telegram", ("telegram", "web", "voice"),
        r("terminal-card-and-main-prose-arrive-once", "delivery_ledger", terminalPresentationCount=1, duplicateProseCount=0),
        r("same-account-completion-coalesces-in-budget", "delivery_ledger", maximumCoalescingMs=2000),
        r("redundant-or-empty-results-remain-durably-silent", "delivery_ledger", durablySilentCount=2, lostTerminalStateCount=0)),
    "PWK-028": _case("voice", ("voice", "web"),
        r("provider-retry-after-uses-structured-evidence", "provider_ledger", structuredRetryAfterCount=1, proseClassifiedFailureCount=0),
        r("fallback-never-downgrades-model-or-effort", "provider_ledger", silentModelDowngradeCount=0, silentEffortDowngradeCount=0),
        r("scheduler-enforces-fair-resource-caps", "capacity_ledger", maximumChildCount=64, maximumThreadCount=2048),
        r("main-and-controls-stay-responsive-at-load", "turn_ledger", responsiveMainCount=1, responsiveControlCount=1)),
    "PWK-029": _case("telegram", ("telegram",),
        r("telegram-handler-families-never-block", "turn_ledger", nonblockingHandlerFamilyCount=5),
        r("tampered-expired-and-cross-user-actions-fail", "authorization_ledger", deniedCapabilityClassCount=4, crossUserEffectCount=0),
        r("double-tap-or-uncertain-response-never-repeats-effect", "action_ledger", duplicateEffectCount=0, truthfulRetryCount=1), restart=True),
    "PWK-030": _case("web", ("web", "telegram"),
        r("unsupported-native-control-planes-stay-disabled", "native_runtime_ledger", disabledCompetingControlPlaneCount=2),
        r("native-child-settles-within-bounded-window", "native_runtime_ledger", settlingTimeoutSeconds=120, lostChildCount=0),
        r("unproven-native-capabilities-remain-false", "native_runtime_ledger", inventedNativeCapabilityCount=0)),
    "PWK-031": _case("web", ("web",),
        r("direct-and-each-worker-path-pass-independently", "quality_scorecard", independentlyPassingPathCount=3, hiddenFailingPathCount=0),
        r("every-quality-dimension-is-scored", "quality_scorecard", scoredDimensionCount=4),
        r("representative-output-and-artifacts-remain-useful", "artifact_ledger", verifiedOutputPathCount=3)),
    "PWK-032": _case("web", ("web", "telegram", "voice"),
        r("rollback-disables-new-automatic-admission", "release_snapshot", effectiveAvailability=False, newAutomaticWorkCount=0),
        r("existing-work-remains-visible-and-controllable", "action_ledger", retainedControllableWorkCount=1),
        r("existing-terminal-callback-delivers-once", "delivery_ledger", deliveredExistingResultCount=1, duplicateDeliveryCount=0), restart=True),
    "PWK-033": _case("web", ("web", "telegram", "voice"),
        r("provider-auth-broker-and-tool-failures-stay-distinct", "fault_ledger", distinctFailureClassCount=9),
        r("warm-resume-rejects-any-authority-fingerprint-change", "authorization_ledger", rejectedFingerprintChangeCount=6),
        r("fallback-never-expands-native-scope", "capability_ledger", unauthorizedFallbackCapabilityCount=0)),
    "PWK-034": _case("voice", ("voice", "web"),
        r("dynamic-capsule-stays-bounded-and-nonpersisted", "prompt_ledger", maximumCapsuleBytes=16384, persistedCapsuleCount=0),
        r("capsule-prioritizes-attention-and-preserves-overflow", "prompt_ledger", prioritizedAttentionCount=2, overflowToolPathCount=1),
        r("voice-receives-only-urgent-counts-until-requested", "prompt_ledger", unsolicitedVoiceDetailCount=0)),
    "PWK-035": _case("web", ("web",),
        r("new-chat-receipt-preserves-one-canonical-route", "turn_ledger", canonicalConversationCount=1, closedStreamCount=0),
        r("delayed-receipt-cannot-reclaim-abandoned-route", "turn_ledger", reclaimedAbandonedRouteCount=0),
        r("lost-response-retry-restores-original-turn", "turn_ledger", stableLogicalTurnCount=1, duplicateConversationCount=0)),
    "PWK-036": _case("web", ("web", "telegram"),
        r("supersession-revokes-only-exact-provider-operation", "turn_ledger", revokedOperationCount=1, cancelledCommittedWorkCount=0),
        r("callback-phase-b-has-no-tools-or-bearer-headers", "authorization_ledger", phaseBToolCount=0, leakedBearerHeaderCount=0),
        r("broker-instruction-retains-scoped-context", "prompt_ledger", preservedInstructionCount=1, leakedRejectedValueCount=0)),
    "PWK-037": _case("telegram", ("telegram", "web"),
        r("telegram-waits-for-exact-account-aware-readiness", "release_snapshot", readyBoundaryCount=1, genericHealthBypassCount=0),
        r("unready-turn-is-rejected-before-ingress", "turn_ledger", preIngressRejectionCount=1, rejectedTurnWorkCount=0),
        r("only-proven-not-accepted-retries-automatically", "action_ledger", safeAutomaticRetryCount=1, ambiguousRetryCount=0), restart=True),
    "PWK-038": _case("telegram", ("telegram", "web"),
        r("every-launch-has-one-exact-replay-fence", "lifecycle_ledger", launchReceiptCount=2, duplicateLaunchCount=0),
        r("main-answers-direct-part-without-competing-reply", "turn_ledger", directAnswerCount=1, competingReplyCount=0),
        r("unreadable-receipt-fails-provider-fallback-closed", "provider_ledger", unreadableReceiptFallbackCount=0)),
    "PWK-039": _case("telegram", ("telegram", "web"),
        r("one-inference-reuses-or-creates-exact-work", "turn_ledger", decisionInferenceCount=1, inventedSupervisorCount=0),
        r("message-preserves-original-objective", "action_ledger", preservedObjectiveCount=1, replacedObjectiveCount=0),
        r("main-never-claims-unsettled-worker-action", "action_ledger", prematureActionClaimCount=0)),
    "PWK-040": _case("telegram", ("telegram", "web"),
        r("graph-coordination-does-not-perform-external-effects", "capability_ledger", unmarkedExternalEffectCount=0),
        r("participant-fallback-remains-inside-same-graph", "provider_ledger", graphLocalFallbackCount=1, outerRecoveryCount=0),
        r("participant-retry-never-duplicates-worker-or-connection", "lifecycle_ledger", duplicateWorkerCount=0, duplicateAccountEffectCount=0), restart=True),
    "PWK-041": _case("telegram", ("telegram", "web"),
        r("current-task-envelope-owns-deliverable-constraints", "prompt_ledger", currentTaskAuthorityCount=1, staleContextConstraintCount=0),
        r("public-ingress-cannot-forge-reserved-task-source", "authorization_ledger", rejectedForgedSourceCount=1),
        r("continuation-preserves-authoritative-artifact", "artifact_ledger", exactDeliverableCount=1)),
    "PWK-042": _case("telegram", ("telegram", "web"),
        r("queued-message-atomically-replaces-same-work-run", "action_ledger", replacementRunCount=1, hiddenSiblingRunCount=0),
        r("never-started-guidance-remains-in-original-order", "action_ledger", preservedGuidanceCount=2),
        r("started-run-message-waits-for-next-boundary", "lifecycle_ledger", interruptedStartedRunCount=0)),
    "PWK-043": _case("web", ("web", "telegram"),
        r("fresh-pressure-releases-only-safe-idle-container", "capacity_ledger", releasedIdleContainerCount=1, releasedActiveContainerCount=0),
        r("capacity-is-measured-before-and-after-release", "capacity_ledger", freshMeasurementCount=2),
        r("released-compute-preserves-durable-workspace", "artifact_ledger", lostWorkspaceCount=0)),
    "PWK-044": _case("telegram", ("telegram", "web"),
        r("continuous-capacity-wait-emits-one-transition", "capacity_ledger", waitTransitionCount=1, duplicateWaitTransitionCount=0),
        r("wait-episode-produces-one-callback-intent", "delivery_ledger", waitCallbackIntentCount=1),
        r("actual-runtime-invocation-starts-new-wait-episode", "lifecycle_ledger", postInvocationEpisodeCount=1)),
    "PWK-045": _case("web", ("web", "telegram"),
        r("sibling-context-never-imposes-artifact-format", "prompt_ledger", siblingConstraintLeakCount=0, currentTaskFormatCount=1),
        r("deliverables-stay-outside-runtime-support-tree", "artifact_ledger", discoverableDeliverableCount=2, supportTreeDeliverableCount=0),
        r("terminal-artifact-discovery-matches-delivery", "delivery_ledger", terminalDeliveredArtifactCount=2), restart=True),
    "PWK-046": _case("web", ("web", "telegram"),
        r("compute-release-reconciles-recorded-prior-session", "native_runtime_ledger", reconciledRecordedSessionCount=1, synthesizedSessionCount=0),
        r("session-clear-compares-exact-process-generation", "native_runtime_ledger", ambiguousSessionClearCount=0, replacementSessionClearCount=0),
        r("released-capacity-recovers-exact-queued-work", "capacity_ledger", recoveredQueuedWorkCount=1), restart=True),
    "PWK-047": _case("telegram", ("telegram", "web"),
        r("independent-account-drafts-create-distinct-work", "lifecycle_ledger", distinctTargetWorkCount=2, duplicateTargetWorkCount=0),
        r("each-target-creates-one-unsent-draft", "capability_ledger", unsentDraftCount=2, sentMessageCount=0),
        r("configured-provider-fallback-keeps-same-work", "provider_ledger", sameWorkFallbackCount=1),
        r("main-remains-responsive-during-account-work", "turn_ledger", concurrentQuickAnswerCount=1), restart=True),
    "PWK-048": _case("web", ("web", "telegram"),
        r("running-requires-immutable-exact-invocation", "lifecycle_ledger", invocationTimestampCount=1, syntheticRunningCount=0),
        r("running-holds-matching-open-attempt-and-live-lease", "capacity_ledger", matchingAttemptCount=1, matchingLeaseCount=1),
        r("retry-and-reconciliation-never-invent-execution", "lifecycle_ledger", inventedRuntimeAttemptCount=0), restart=True),
    "PWK-049": _case("web", ("web", "telegram"),
        r("producer-trace-is-exact-owner-scoped-and-immutable", "trace_ledger", ownerScopedTraceCount=1, mutatedTraceCount=0),
        r("attempt-and-callback-histories-remain-bounded", "trace_ledger", overflowAcceptanceCount=0, stableAttemptIdentityCount=1),
        r("callback-http-acceptance-is-not-user-delivery", "delivery_ledger", transportOnlyAcceptanceCount=1, falseDeliveredCount=0),
        r("public-artifact-fields-contain-only-safe-hashes", "artifact_ledger", leakedRawIdentityCount=0)),
    "PWK-UC-001": _case("telegram", ("telegram", "web"),
        r("rapid-a-b-c-creates-two-workers-and-one-answer", "turn_ledger", durableWorkCount=2, directQuickAnswerCount=1),
        r("natural-follow-up-reuses-exact-existing-work", "action_ledger", reusedWorkCount=1, duplicateWorkCount=0),
        r("active-workers-remain-controllable-across-surfaces", "lifecycle_ledger", controllableWorkCount=2), restart=True),
    "PWK-UC-002": _case("web", ("web", "telegram", "voice"),
        r("empty-stale-unavailable-and-overflow-stay-distinct", "account_ledger", distinctRosterStateCount=4),
        r("rollback-preserves-existing-visible-work", "lifecycle_ledger", retainedVisibleWorkCount=1, hiddenExistingWorkCount=0)),
    "PWK-UC-003": _case("web", ("web", "telegram", "voice"),
        r("every-control-is-exact-and-idempotent", "action_ledger", distinctActionCount=9, duplicateEffectCount=0),
        r("a-only-control-never-changes-b", "lifecycle_ledger", controlledWorkCount=1, siblingMutationCount=0),
        r("lost-response-recovers-original-receipt", "action_ledger", recoveredReceiptCount=1), restart=True),
    "PWK-UC-004": _case("voice", ("voice", "web", "telegram"),
        r("every-authorized-input-memory-and-tool-is-preserved", "capability_ledger", authorizedCapabilityFamilyCount=8, missingCapabilityCount=0),
        r("fallback-controls-and-retry-retain-exact-scope", "provider_ledger", scopedExecutionBoundaryCount=4, unauthorizedCapabilityCount=0),
        r("every-result-is-delivered-once-on-linked-surfaces", "delivery_ledger", deliveredResultCount=2, duplicateResultCount=0),
        r("missing-auth-quota-capacity-and-input-remain-typed", "fault_ledger", recoverableFailureClassCount=7), restart=True),
    "PWK-UC-005": _case("telegram", ("telegram", "web", "voice"),
        r("moved-archived-and-deleted-origins-preserve-work", "turn_ledger", coveredOriginStateCount=3, recreatedDeletedThreadCount=0),
        r("every-required-destination-receives-one-main-result", "delivery_ledger", destinationCount=3, duplicateDeliveryCount=0),
        r("scheduled-completion-waits-for-all-workers", "scheduler_ledger", requiredWorkerCount=2, prematureScheduleCompletionCount=0), restart=True),
    "PWK-UC-006": _case("web", ("web", "telegram"),
        r("codex-and-claude-project-only-proven-children", "native_runtime_ledger", provenProviderFamilyCount=2, inventedChildCount=0),
        r("native-stop-leaves-no-unrelated-session-or-orphan", "action_ledger", unrelatedSessionExposureCount=0, orphanProcessCount=0), restart=True),
    "PWK-UC-007": _case("api", ("web",),
        r("unsafe-host-worker-disables-automatic-admission", "release_snapshot", effectiveAvailability=False),
        r("isolated-worker-cannot-spawn-or-inspect-peers", "security_probe", deniedPeerOperationCount=2, successfulPeerOperationCount=0),
        r("two-owner-boundaries-remain-independent", "authorization_ledger", ownerBoundaryCount=2, crossOwnerLeakCount=0)),
    "PWK-UC-008": _case("installer", ("web", "telegram", "voice"),
        r("clean-install-aligns-every-shipped-identity", "component_identity", alignedIdentityLayerCount=5, dirtyComponentCount=0),
        r("default-install-remains-focused-and-dark", "release_snapshot", defaultParallelAvailability=False, defaultMode="focused"),
        r("rollback-keeps-existing-visible-controllable-work", "action_ledger", retainedControllableWorkCount=1), restart=True),
    "PWK-UC-009": _case("voice", ("voice", "web"),
        r("main-and-exact-steer-remain-fast-at-max-load", "turn_ledger", responsiveQuickTurnCount=1, responsiveSteerCount=1),
        r("weighted-queue-keeps-owner-fairness", "capacity_ledger", representedOwnerCount=2, starvationCount=0),
        r("structured-quota-preserves-model-effort-and-retry", "provider_ledger", authoritativeRetryAfterCount=1, silentDowngradeCount=0)),
    "PWK-UC-010": _case("web", ("web", "telegram", "voice"),
        r("simultaneous-completions-coalesce-within-budget", "delivery_ledger", maximumCoalescingMs=2000, duplicateCompletionCount=0),
        r("redundant-completion-stays-durably-silent", "delivery_ledger", silentRedundantResultCount=1, lostTerminalResultCount=0),
        r("reconnected-stream-preserves-one-visible-result", "turn_ledger", visibleCompletionCount=1)),
    "PWK-UC-011": _case("web", ("web",),
        r("direct-codex-and-claude-each-meet-quality", "quality_scorecard", independentlyPassingPathCount=3),
        r("all-four-quality-dimensions-pass-per-path", "quality_scorecard", passingDimensionCount=4, concealedFailingPathCount=0),
        r("quality-does-not-degrade-for-speed", "provider_ledger", qualityRegressingOptimizationCount=0)),
    "PWK-UC-012": _case("web", ("web", "telegram", "voice"),
        r("disabled-admission-never-creates-new-worker", "release_snapshot", automaticAdmissionCount=0),
        r("existing-work-survives-lowered-capacity-and-control", "action_ledger", retainedControllableWorkCount=1),
        r("existing-completion-delivers-after-rollback", "delivery_ledger", deliveredExistingResultCount=1), restart=True),
    "PWK-UC-013": _case("telegram", ("telegram", "web", "voice"),
        r("moved-archived-deleted-origins-preserve-continuity", "turn_ledger", coveredOriginStateCount=3, recreatedDeletedThreadCount=0),
        r("main-authors-only-one-useful-continuation", "delivery_ledger", mainAuthoredContinuationCount=1, duplicateContinuationCount=0),
        r("redundant-result-remains-silent-with-terminal-truth", "delivery_ledger", silentRedundantResultCount=1, lostTerminalResultCount=0), restart=True),
    "REL-001": _case("cli", (),
        r("zero-private-identifiers", "repository_scan", privateFindingCount=0),
        r("public-diff-has-no-whitespace-or-secret-leak", "repository_scan", diffErrorCount=0, secretFindingCount=0)),
    "REL-002": _case("cli", (),
        r("nested-source-review-complete", "component_identity", reviewedNestedComponentCount=2),
        r("nested-tests-pass-before-parent-pin-change", "component_identity", unreviewedNestedChangeCount=0, failingNestedTestCount=0)),
    "REL-003": _case("cli", (),
        r("parent-pin-equals-component-revision", "component_identity", mismatchedComponentPinCount=0),
        r("installed-component-build-matches-pinned-source", "component_identity", matchedComponentLayerCount=3)),
    "REL-004": _case("web", ("web",),
        r("required-background-cards-are-visible", "delivery_ledger", requiredVisibleCardCount=2, visibleErrorBannerCount=0),
        r("background-cards-persist-after-reload", "delivery_ledger", persistedTerminalCardCount=2),
        r("main-answer-never-contradicts-terminal-insight", "turn_ledger", contradictoryAnswerCount=0)),
    "REL-005": _case("cli", (),
        r("zero-cross-project-markers", "repository_scan", crossProjectFindingCount=0),
        r("public-qa-evidence-has-no-private-owner-data", "repository_scan", ownerDataFindingCount=0)),
    "REL-006": _case("cli", (),
        r("open-gates-keep-feature-dark", "release_snapshot", defaultParallelAvailability=False, defaultMode="focused"),
        r("every-required-case-is-accounted-for", "release_snapshot", unaccountedRequiredCaseCount=0),
        r("local-override-is-always-marked-not-ready", "release_snapshot", unlabelledLocalOverrideCount=0, falseReadyClaimCount=0)),
    "REL-UC-001": _case("cli", (),
        r("public-diff-user-path-clean", "repository_scan", privateFindingCount=0),
        r("public-artifacts-contain-only-approved-placeholders", "repository_scan", unsafePublicArtifactCount=0)),
    "REL-UC-002": _case("cli", (),
        r("degraded-scan-reports-unavailable", "repository_scan", typedDegradedOutcomeCount=1),
        r("missing-setup-or-auth-never-claims-clean-pass", "repository_scan", fabricatedCleanPassCount=0)),
    "REL-UC-003": _case("cli", (),
        r("component-boundary-survives-restart", "component_identity", preservedComponentIdentityCount=2),
        r("post-restart-wording-matches-installed-component", "release_snapshot", contradictoryReadinessClaimCount=0), restart=True),
}
del r


def _validate_catalog() -> None:
    expected = {
        *(f"PWK-{number:03d}" for number in range(1, 50)),
        *(f"PWK-UC-{number:03d}" for number in range(1, 14)),
        *(f"REL-{number:03d}" for number in range(1, 7)),
        *(f"REL-UC-{number:03d}" for number in range(1, 4)),
    }
    if set(CASE_SPECS) != expected or len(CASE_SPECS) != 71:
        raise ValueError("catalog verifier does not own the exact 71 missing cases")


_validate_catalog()


def registration_contract() -> dict[str, dict[str, object]]:
    """Return the exact parent registration contract without changing its registry."""

    return {
        case_id: {"id": VERIFIER_ID, "path": REGISTRATION_PATH}
        for case_id in CASE_SPECS
    }


def case_requirements(case_id: str) -> tuple[Requirement, ...]:
    spec = CASE_SPECS.get(case_id)
    if spec is None:
        raise ValueError("catalog case is unsupported or owns a dedicated verifier")
    result = [
        _requirement("installed-runtime-identity", "installed_identity", processIdentityCount=1),
        *spec.requirements,
    ]
    for surface in sorted(spec.capture_surfaces):
        result.append(
            _requirement(
                f"visible-installed-{surface}-user-path",
                f"{surface}_observation",
                captureCount=1,
                visibleRecordCount=1,
            )
        )
    if spec.restart_required:
        result.append(
            _requirement(
                "restart-exact-process-recovery",
                "restart_ledger",
                restartedServiceCount=1,
            )
        )
    return tuple(result)


def _invalid(message: str = "installed catalog semantic evidence is invalid") -> NoReturn:
    raise ValueError(message)


def _object(value: object, fields: frozenset[str] | set[str]) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != set(fields):
        _invalid("catalog producer record shape is invalid")
    return value


def _hash(value: object, *, reference: bool = False) -> str:
    expression = SHA256_REF if reference else SHA256
    if not isinstance(value, str) or expression.fullmatch(value) is None:
        _invalid("catalog owner, candidate, artifact, or source hash is invalid")
    return value


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            _invalid("catalog evidence contains duplicate JSON fields")
        result[key] = value
    return result


def _strict_json(raw: bytes) -> object:
    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=lambda _value: _invalid("catalog evidence contains nonfinite numbers"),
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("catalog producer record JSON is invalid") from exc


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        _invalid("catalog evidence timestamp is invalid")
    try:
        result = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("catalog evidence timestamp is invalid") from exc
    if result.tzinfo is None or result.utcoffset() != timedelta(0):
        _invalid("catalog evidence timestamp must be UTC")
    return result.astimezone(timezone.utc)


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        _invalid("catalog installed producer authority is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _private_root(path: Path) -> Path:
    supplied = Path(path).expanduser()
    try:
        if supplied.is_symlink():
            _invalid("catalog private evidence root is invalid")
        root = supplied.resolve(strict=True)
        metadata = root.stat()
    except (OSError, RuntimeError) as exc:
        raise ValueError("catalog private evidence root is invalid") from exc
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) != 0o700
    ):
        _invalid("catalog private evidence root is invalid")
    try:
        root.relative_to(Path(__file__).resolve().parents[3])
    except ValueError:
        return root
    _invalid("catalog private user evidence cannot enter the public repository")


def _private_file(relative: object, *, root: Path) -> tuple[bytes, str]:
    if not isinstance(relative, str) or not relative or "\\" in relative:
        _invalid("catalog private evidence path is invalid")
    lexical = Path(relative)
    if (
        lexical.is_absolute()
        or lexical.as_posix() != relative
        or any(SAFE_COMPONENT.fullmatch(part) is None for part in lexical.parts)
    ):
        _invalid("catalog private evidence path is invalid")
    current = root
    for part in lexical.parts[:-1]:
        current = current / part
        try:
            metadata = current.lstat()
        except OSError as exc:
            raise ValueError("catalog private evidence path is invalid") from exc
        if (
            not stat.S_ISDIR(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or stat.S_IMODE(metadata.st_mode) != 0o700
        ):
            _invalid("catalog private evidence path is invalid")
    target = current / lexical.name
    descriptor: int | None = None
    try:
        descriptor = os.open(
            target,
            os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or stat.S_IMODE(metadata.st_mode) != 0o600
            or metadata.st_nlink != 1
            or not 0 < metadata.st_size <= MAX_FILE_BYTES
        ):
            _invalid("catalog private evidence file is unsafe")
        content = bytearray()
        while len(content) <= MAX_FILE_BYTES:
            chunk = os.read(descriptor, min(1024 * 1024, MAX_FILE_BYTES + 1 - len(content)))
            if not chunk:
                break
            content.extend(chunk)
        after = os.fstat(descriptor)
        current_metadata = target.lstat()
        if (
            len(content) != metadata.st_size
            or len(content) > MAX_FILE_BYTES
            or (metadata.st_dev, metadata.st_ino, metadata.st_mtime_ns, metadata.st_size)
            != (after.st_dev, after.st_ino, after.st_mtime_ns, after.st_size)
            or (metadata.st_dev, metadata.st_ino) != (current_metadata.st_dev, current_metadata.st_ino)
        ):
            _invalid("catalog private evidence changed during verification")
    except (OSError, RuntimeError) as exc:
        raise ValueError("catalog private evidence file is unavailable") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
    return bytes(content), lexical.as_posix()


def _signed_source_receipts(
    evidence: object,
    *,
    root: Path,
    service_ids: set[str],
    case_id: str,
    owner_ref_hash: str,
    candidate_digest: str,
    artifact_digest: str,
    session_ref: str,
    source_verifier: Callable[[Mapping[str, object], ProducerSpec], None],
) -> dict[str, dict[str, object]]:
    if (
        not isinstance(evidence, list)
        or not evidence
        or len(evidence) > MAX_EVIDENCE_FILES
    ):
        _invalid("catalog protected producer evidence is unavailable")
    receipts: dict[str, dict[str, object]] = {}
    for supplied in evidence:
        entry = _object(supplied, EVIDENCE_FIELDS)
        kind = str(entry.get("kind") or "")
        if kind.endswith("_capture"):
            continue
        producer = EVIDENCE_PRODUCERS.get(kind)
        if producer is None or producer.service_id not in service_ids:
            _invalid("catalog protected producer service is invalid")
        raw, _path = _private_file(entry.get("path"), root=root)
        if not hmac.compare_digest(
            hashlib.sha256(raw).hexdigest(), _hash(entry.get("sha256"))
        ):
            _invalid("catalog protected producer evidence digest is invalid")
        document = _object(_strict_json(raw), DOCUMENT_FIELDS)
        source = _object(document.get("sourceReceipt"), SOURCE_RECEIPT_FIELDS)
        reference = _hash(source.get("sourceRefHash"))
        if (
            reference in receipts
            or len(receipts) >= MAX_SOURCE_RECEIPTS
            or source.get("contractVersion") != CONTRACT_VERSION
            or source.get("caseId") != case_id
            or source.get("ownerRefHash") != owner_ref_hash
            or source.get("candidateDigest") != candidate_digest
            or source.get("artifactDigest") != artifact_digest
            or source.get("sessionRef") != session_ref
            or source.get("serviceId") != producer.service_id
            or source.get("producerId") != producer.producer_id
        ):
            _invalid("catalog protected producer source is duplicated or cross-account")
        try:
            source_verifier(source, producer)
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
            raise ValueError("catalog protected producer signature is invalid") from exc
        receipts[reference] = source
    if not receipts:
        _invalid("catalog publisher-signed producer receipts are unavailable")
    return receipts


def _publisher_trust_policy(
    *,
    gate: ModuleType,
    installed_root: Path,
    runtime_owner_state: Path,
    candidate_digest: str,
) -> tuple[ModuleType, object]:
    """Reuse the release evaluator's publisher root and protected witness."""

    resolver = getattr(gate, "_resolve_external_release_attestation_authority", None)
    context_resolver = getattr(gate, "_external_release_attestation_context", None)
    if not callable(resolver) or not callable(context_resolver):
        _invalid("catalog publisher-authenticated release trust is unavailable")
    trusted = resolver(
        installed_root=installed_root,
        runtime_owner_state=runtime_owner_state,
        candidate_digest=candidate_digest,
    )
    context = context_resolver(
        trusted,
        installed_root=installed_root,
        runtime_owner_state=runtime_owner_state,
        candidate_digest=candidate_digest,
    )
    if not isinstance(context, tuple) or len(context) != 4:
        _invalid("catalog publisher-authenticated release trust is unavailable")
    attestation, policy, _ledger, _witness = context
    if (
        getattr(policy, "candidate_digest", None) != candidate_digest
        or SHA256.fullmatch(str(getattr(policy, "policy_sha256", ""))) is None
        or getattr(policy, "policy_sha256", None)
        != getattr(trusted, "expected_policy_sha256", None)
        or getattr(policy, "installed_root", None) != installed_root
    ):
        _invalid("catalog publisher-authenticated release policy is invalid")
    return attestation, policy


def _protected_source_verifier(
    attestation: ModuleType,
    policy: object,
    *,
    case_id: str,
) -> Callable[[Mapping[str, object], ProducerSpec], None]:
    """Bind every source receipt to a publisher-approved external signer."""

    spec = CASE_SPECS.get(case_id)
    metadata = attestation.release_attestation_metadata(policy, case_id=case_id)
    case = policy.cases.get(case_id)
    if (
        spec is None
        or case is None
        or case.surface != spec.surface
        or case.verifier_id != VERIFIER_ID
        or metadata.get("algorithm") != "ssh-ed25519"
        or metadata.get("requiresExternalPublisherSigner") is not True
    ):
        _invalid("catalog publisher-approved case, surface, or verifier is invalid")

    def verify(source: Mapping[str, object], producer: ProducerSpec) -> None:
        signer_id = str(source.get("signerId") or "")
        signer = policy.producers.get(signer_id)
        if signer is None:
            _invalid("catalog producer signer is not publisher-approved")
        approved_observer = (
            signer.role == "observation" and signer_id in case.producer_ids
        )
        approved_service = (
            signer.role == "service"
            and signer_id in case.service_producer_ids
            and signer.service_id == producer.service_id
        )
        if (
            not (approved_observer or approved_service)
            or source.get("signerIdentity") != signer.identity
            or source.get("surface") != case.surface
            or source.get("verifierId") != case.verifier_id
        ):
            _invalid("catalog producer signer does not own this exact case or service")
        unsigned = {
            field: value for field, value in source.items() if field != "signature"
        }
        try:
            attestation._verify_signature(
                (_canonical(unsigned) + "\n").encode("utf-8"),
                source.get("signature"),
                policy=policy,
                identity=signer.identity,
                namespace=SOURCE_SIGNATURE_NAMESPACE,
                label="catalog producer source",
            )
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
            raise ValueError("catalog protected producer signature is invalid") from exc

    return verify


def probe_live_authority(
    *,
    case_id: str,
    owner_ref_hash: str,
    session_ref: str,
    evidence_root: Path,
    evidence: object,
    now: datetime | None = None,
) -> LiveAuthority:
    """Resolve publisher-attested ordinary captures without fault-injection sessions."""

    forbidden = {
        "VIVENTIUM_APP_SUPPORT_DIR",
        "VIVENTIUM_RUNTIME_DIR",
        "VIVENTIUM_RUNTIME_PROFILE",
        "VIVENTIUM_LOCAL_QA_CASE_ID",
        "VIVENTIUM_LOCAL_QA_CASE_TOKEN",
        "VIVENTIUM_LOCAL_QA_SESSION_REF",
        "VIVENTIUM_LOCAL_QA_MODE",
        "VIVENTIUM_LOCAL_QA_COMPONENT_ARTIFACT_DIGEST",
    }
    if any(name in os.environ for name in forbidden):
        _invalid("catalog installed producer authority is unavailable")
    try:
        home = Path(pwd.getpwuid(os.getuid()).pw_dir).resolve(strict=True)
        support = home / "Library" / "Application Support" / "Viventium"
        runtime = support / "runtime"
        owner_path = support / "state" / "runtime" / "isolated" / "stack-owner.json"
        installed = Path(__file__).resolve().parents[3]
        gate = _load_module(
            installed / "scripts/viventium/parallel_work_release_gate.py",
            "viventium_catalog_live_release_gate",
        )
        if not gate._runtime_owner_state_proves_active(installed, owner_path):
            _invalid("catalog installed owner identity is not active")
        control = _load_module(
            installed / "scripts/viventium/local_qa_runtime_control.py",
            "viventium_catalog_live_runtime_control",
        )
        _raw_owner, owner = control._read_private_json(
            owner_path, label="installed runtime owner", max_bytes=64 * 1024
        )
        if not isinstance(owner, dict):
            _invalid("catalog installed owner identity is invalid")
        identity_path = runtime / "parallel-work-artifact-identity.json"
        _raw_identity, identity = control._read_private_json(
            identity_path, label="installed artifact identity", max_bytes=128 * 1024
        )
        candidate, artifact = gate._qa_candidate_digests(identity)
        candidate = _hash(candidate)
        artifact = _hash(artifact)
        account_owner = _hash(owner_ref_hash)
        if SESSION_REF.fullmatch(session_ref) is None:
            _invalid("catalog protected producer capture reference is invalid")
        attestation, policy = _publisher_trust_policy(
            gate=gate,
            installed_root=installed,
            runtime_owner_state=owner_path,
            candidate_digest=candidate,
        )
        source_verifier = _protected_source_verifier(
            attestation, policy, case_id=case_id
        )
        acknowledgement = _load_module(
            installed / "scripts/viventium/local_qa_service_ack.py",
            "viventium_catalog_live_service_ack",
        )
        owner_process = acknowledgement.probe_process(
            int(owner["ownerPid"]), Path(str(owner["ownerExecutablePath"]))
        )
        owner_process = {field: owner_process[field] for field in PROCESS_FIELDS}
        services = {
            EVIDENCE_PRODUCERS[requirement.kind].service_id
            for requirement in case_requirements(case_id)
        }
        receipts = _signed_source_receipts(
            evidence,
            root=_private_root(evidence_root),
            service_ids=services,
            case_id=case_id,
            owner_ref_hash=account_owner,
            candidate_digest=candidate,
            artifact_digest=artifact,
            session_ref=session_ref,
            source_verifier=source_verifier,
        )
        processes: dict[str, dict[str, object]] = {}
        for receipt in receipts.values():
            service_id = str(receipt.get("serviceId") or "")
            if service_id not in services:
                _invalid("catalog authoritative producer service is invalid")
            process = _object(receipt.get("processIdentity"), PROCESS_FIELDS)
            previous = processes.get(service_id)
            if previous is not None and _digest(previous) != _digest(process):
                _invalid("catalog producer process identity changed during capture")
            processes[service_id] = dict(process)
        if (
            set(processes) != services
            or "runtime-owner" not in processes
            or _digest(processes["runtime-owner"]) != _digest(owner_process)
        ):
            _invalid("catalog producer processes do not match the live installed owner")
        checked = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        maximum_age = int(policy.maximum_receipt_age_seconds)
        future_skew = int(policy.maximum_future_skew_seconds)
        return LiveAuthority(
            candidate_digest=candidate,
            artifact_digest=artifact,
            owner_ref_hash=account_owner,
            case_id=case_id,
            session_ref=session_ref,
            session_started_at=checked - timedelta(seconds=maximum_age),
            session_expires_at=checked + timedelta(seconds=max(future_skew, 1)),
            producer_processes=processes,
            producer_receipts=receipts,
            source_signature_verifier=source_verifier,
        )
    except (
        AttributeError,
        ImportError,
        KeyError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as exc:
        raise ValueError("catalog installed producer authority is unavailable") from exc


def _png_capture(raw: bytes) -> dict[str, int]:
    message = "catalog visible user capture is not a real installed screenshot"
    if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        _invalid(message)
    offset = 8
    width = height = channels = 0
    compressed = bytearray()
    header = end_seen = False
    while offset + 12 <= len(raw):
        length = struct.unpack(">I", raw[offset : offset + 4])[0]
        end = offset + length + 12
        if length > MAX_FILE_BYTES or end > len(raw):
            _invalid(message)
        kind = raw[offset + 4 : offset + 8]
        payload = raw[offset + 8 : offset + 8 + length]
        crc = struct.unpack(">I", raw[offset + 8 + length : end])[0]
        if zlib.crc32(kind + payload) & 0xFFFFFFFF != crc:
            _invalid(message)
        if kind == b"IHDR":
            if header or offset != 8 or length != 13:
                _invalid(message)
            width, height, depth, color, compression, filtering, interlace = struct.unpack(
                ">IIBBBBB", payload
            )
            channels = {0: 1, 2: 3, 4: 2, 6: 4}.get(color, 0)
            if (
                width < 320
                or height < 180
                or width * height > MAX_CAPTURE_PIXELS
                or depth != 8
                or not channels
                or compression != 0
                or filtering != 0
                or interlace != 0
            ):
                _invalid(message)
            header = True
        elif kind == b"IDAT":
            if not header or end_seen:
                _invalid(message)
            compressed.extend(payload)
        elif kind == b"IEND":
            if not header or length or end != len(raw):
                _invalid(message)
            end_seen = True
            break
        offset = end
    if not header or not end_seen or not compressed:
        _invalid(message)
    expected = height * (1 + width * channels)
    try:
        decoder = zlib.decompressobj()
        pixels = decoder.decompress(bytes(compressed), expected + 1)
        pixels += decoder.flush()
    except zlib.error as exc:
        raise ValueError(message) from exc
    if len(pixels) != expected or decoder.unused_data or decoder.unconsumed_tail:
        _invalid(message)
    stride = 1 + width * channels
    if any(pixels[row * stride] > 4 for row in range(height)):
        _invalid(message)
    sample = pixels[1 : min(len(pixels), 65_536)]
    if len(set(sample)) < 16 or max(sample) - min(sample) < 24:
        _invalid(message)
    return {"height": height, "width": width}


def _audible_capture(raw: bytes) -> dict[str, int]:
    message = "catalog audible Voice user capture is missing or silent"
    try:
        with wave.open(io.BytesIO(raw), "rb") as recording:
            channels = recording.getnchannels()
            sample_width = recording.getsampwidth()
            rate = recording.getframerate()
            frames = recording.getnframes()
            if channels not in {1, 2} or sample_width != 2 or rate < 8_000 or frames < rate:
                _invalid(message)
            samples = recording.readframes(min(frames, rate * 2))
            values = struct.unpack(f"<{len(samples) // 2}h", samples)
            if not values or max(abs(sample) for sample in values) < 256:
                _invalid(message)
    except (EOFError, OSError, struct.error, wave.Error) as exc:
        raise ValueError(message) from exc
    return {"frames": frames, "rate": rate}


def _authority(
    authority: object,
    *,
    case_id: str,
    candidate: str,
    artifact: str,
    owner: str,
    session_ref: str,
    run_at: datetime,
    now: datetime,
) -> LiveAuthority:
    if not isinstance(authority, LiveAuthority):
        _invalid("catalog live installed producer authority is invalid")
    if (
        authority.case_id != case_id
        or authority.candidate_digest != candidate
        or authority.artifact_digest != artifact
        or authority.owner_ref_hash != owner
        or authority.session_ref != session_ref
        or SESSION_REF.fullmatch(session_ref) is None
        or not authority.session_started_at <= run_at < authority.session_expires_at
        or not authority.session_started_at <= now < authority.session_expires_at
        or not isinstance(authority.producer_processes, Mapping)
        or not isinstance(authority.producer_receipts, Mapping)
        or not callable(authority.source_signature_verifier)
    ):
        _invalid("catalog installed owner, candidate, artifact, or session does not match")
    return authority


def _verified_source_receipt(
    receipt: object,
    *,
    document: dict[str, object],
    authority: LiveAuthority,
    producer: ProducerSpec,
    payload: dict[str, object],
    observed_at: datetime,
    used_sources: set[str],
    used_sequences: set[tuple[str, int]],
) -> None:
    source = _object(receipt, SOURCE_RECEIPT_FIELDS)
    reference = _hash(source.get("sourceRefHash"))
    live_source = authority.producer_receipts.get(reference)
    process = authority.producer_processes.get(producer.service_id)
    if (
        not isinstance(live_source, Mapping)
        or not isinstance(process, Mapping)
        or not hmac.compare_digest(_digest(dict(live_source)), _digest(source))
    ):
        _invalid("catalog source receipt is absent from the authoritative live producer")
    process_record = _object(dict(process), PROCESS_FIELDS)
    if (
        type(process_record.get("pid")) is not int
        or int(process_record["pid"]) < 2
        or SHA256_REF.fullmatch(str(process_record.get("startMarker") or "")) is None
        or SHA256_REF.fullmatch(str(process_record.get("executableSha256") or "")) is None
    ):
        _invalid("catalog producer process identity is invalid")
    process_started = _timestamp(process_record.get("startedAt"))
    if process_started > observed_at:
        _invalid("catalog producer process did not exist at the observed capture")
    if (
        source.get("contractVersion") != CONTRACT_VERSION
        or source.get("caseId") != document.get("caseId")
        or source.get("candidateDigest") != authority.candidate_digest
        or source.get("artifactDigest") != authority.artifact_digest
        or source.get("ownerRefHash") != authority.owner_ref_hash
        or source.get("sessionRef") != authority.session_ref
        or source.get("serviceId") != producer.service_id
        or source.get("producerId") != producer.producer_id
        or source.get("processIdentity") != process_record
        or source.get("processStartMarker") != process_record.get("startMarker")
        or source.get("payloadSha256") != _digest(payload)
        or source.get("surface") != document.get("originSurface")
        or source.get("verifierId") != VERIFIER_ID
        or _timestamp(source.get("observedAt")) != observed_at
        or type(source.get("sequence")) is not int
        or int(source["sequence"]) <= 0
        or reference in used_sources
        or (producer.service_id, int(source["sequence"])) in used_sequences
        or not isinstance(source.get("signature"), str)
        or not str(source["signature"]).startswith("-----BEGIN SSH SIGNATURE-----\n")
    ):
        _invalid("catalog authoritative producer receipt does not match its installed evidence")
    try:
        authority.source_signature_verifier(source, producer)
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
        raise ValueError("catalog authoritative producer signature is invalid") from exc
    used_sources.add(reference)
    used_sequences.add((producer.service_id, int(source["sequence"])))


def _verified_records(
    payload: object,
    *,
    kind: str,
    required: Mapping[str, Requirement],
    owner: str,
    observed_at: datetime,
    authority: LiveAuthority,
    records: dict[str, dict[str, object]],
) -> dict[str, object]:
    value = _object(payload, frozenset({"records"}))
    entries = value.get("records")
    if not isinstance(entries, list) or not entries or len(entries) > 128:
        _invalid("catalog producer record or assertion is invalid")
    for item in entries:
        record = _object(item, OBSERVATION_FIELDS)
        check_id = record.get("observationId")
        requirement = required.get(str(check_id or ""))
        if (
            not isinstance(check_id, str)
            or requirement is None
            or requirement.kind != kind
            or check_id in records
            or record.get("ownerRefHash") != owner
            or SHA256.fullmatch(str(record.get("sourceRefHash") or "")) is None
        ):
            _invalid("catalog required observation is invalid, cross-owner, or duplicated")
        captured = _timestamp(record.get("recordedAt"))
        if not authority.session_started_at <= captured <= observed_at:
            _invalid("catalog producer observation timestamp is stale")
        facts = record.get("facts")
        if not isinstance(facts, dict):
            _invalid("catalog authoritative measurement is invalid")
        expected = dict(requirement.facts)
        dynamic: set[str] = set()
        if check_id == "installed-runtime-identity":
            dynamic = {"candidateDigest", "artifactDigest", "ownerRefHash", "activeProcessCount"}
        elif check_id == "restart-exact-process-recovery":
            dynamic = {
                "beforeProcessRefHash",
                "afterProcessRefHash",
                "beforeAt",
                "afterAt",
                "restoredRecordCount",
                "duplicateEffectCount",
            }
        elif kind.endswith("_observation"):
            dynamic = {"captureSha256", "sourceRecordRefHash"}
            if kind == "voice_observation":
                dynamic.add("audibleFrameCount")
            else:
                dynamic.update({"viewportHeight", "viewportWidth"})
        if set(facts) != set(expected) | dynamic:
            _invalid("catalog authoritative measurement shape is invalid")
        for field, expected_value in expected.items():
            actual = facts.get(field)
            if type(actual) is not type(expected_value):
                _invalid("catalog measurement did not match the authoritative producer record")
            if field in {"maximumOverheadMs", "maximumCoalescingMs"}:
                valid = 0 <= actual <= expected_value
            else:
                valid = actual == expected_value
            if not valid:
                _invalid("catalog measurement did not match the authoritative producer record")
        records[check_id] = record
    return value


def _verified_evidence(
    raw: object,
    *,
    root: Path,
    case_id: str,
    spec: CaseSpec,
    requirements: Mapping[str, Requirement],
    owner: str,
    authority: LiveAuthority,
    run_at: datetime,
) -> tuple[list[dict[str, str]], dict[str, dict[str, object]], dict[str, dict[str, int]]]:
    required_document_kinds = {requirement.kind for requirement in requirements.values()}
    required_capture_kinds = {f"{surface}_capture" for surface in spec.capture_surfaces}
    required_kinds = required_document_kinds | required_capture_kinds
    if not isinstance(raw, list) or not raw or len(raw) > MAX_EVIDENCE_FILES:
        _invalid("catalog installed user or producer evidence is unavailable")
    supplied_kinds = {
        str(item.get("kind") or "")
        for item in raw
        if isinstance(item, dict)
    }
    if not required_capture_kinds <= supplied_kinds:
        _invalid("required visible or audible user capture is missing")
    if supplied_kinds != required_kinds or len(raw) != len(required_kinds):
        _invalid("catalog authoritative producer evidence is missing or duplicated")
    records: dict[str, dict[str, object]] = {}
    captures: dict[str, dict[str, int]] = {}
    receipts: list[dict[str, str]] = []
    used_ids: set[str] = set()
    used_paths: set[str] = set()
    used_sources: set[str] = set()
    used_sequences: set[tuple[str, int]] = set()
    total_bytes = 0
    for supplied in raw:
        entry = _object(supplied, EVIDENCE_FIELDS)
        evidence_id = str(entry.get("id") or "")
        kind = str(entry.get("kind") or "")
        if (
            SAFE_COMPONENT.fullmatch(evidence_id) is None
            or evidence_id != kind
            or evidence_id in used_ids
            or kind not in required_kinds
        ):
            _invalid("catalog producer evidence identity is invalid or duplicated")
        content, relative = _private_file(entry.get("path"), root=root)
        total_bytes += len(content)
        measured = hashlib.sha256(content).hexdigest()
        if (
            total_bytes > MAX_TOTAL_BYTES
            or relative in used_paths
            or not hmac.compare_digest(measured, _hash(entry.get("sha256")))
        ):
            _invalid("catalog producer evidence digest or path is invalid")
        receipts.append({"kind": kind, "path": relative, "sha256": measured})
        used_ids.add(evidence_id)
        used_paths.add(relative)
        if kind in required_capture_kinds:
            surface = kind.removesuffix("_capture")
            if surface == "voice":
                if not relative.endswith(".wav"):
                    _invalid("catalog audible Voice capture is invalid")
                captures[surface] = _audible_capture(content)
            else:
                if not relative.endswith(".png"):
                    _invalid("catalog visible screenshot capture is invalid")
                captures[surface] = _png_capture(content)
            captures[surface]["sha256"] = measured
            continue
        if not relative.endswith(".json"):
            _invalid("catalog authoritative producer record is not JSON")
        document = _object(_strict_json(content), DOCUMENT_FIELDS)
        producer = EVIDENCE_PRODUCERS.get(kind)
        if (
            producer is None
            or document.get("contractVersion") != CONTRACT_VERSION
            or document.get("caseId") != case_id
            or document.get("kind") != kind
            or document.get("candidateDigest") != authority.candidate_digest
            or document.get("artifactDigest") != authority.artifact_digest
            or document.get("ownerRefHash") != owner
            or document.get("originSurface") != spec.surface
            or document.get("sessionRef") != authority.session_ref
            or document.get("producerId") != producer.producer_id
            or document.get("serviceId") != producer.service_id
        ):
            _invalid("catalog producer case, owner, surface, artifact, or authority is invalid")
        observed_at = _timestamp(document.get("observedAt"))
        if not authority.session_started_at <= observed_at <= run_at:
            _invalid("catalog producer evidence timestamp is stale or in the future")
        payload = _verified_records(
            document.get("payload"),
            kind=kind,
            required=requirements,
            owner=owner,
            observed_at=observed_at,
            authority=authority,
            records=records,
        )
        _verified_source_receipt(
            document.get("sourceReceipt"),
            document=document,
            authority=authority,
            producer=producer,
            payload=payload,
            observed_at=observed_at,
            used_sources=used_sources,
            used_sequences=used_sequences,
        )
    if set(records) != set(requirements):
        _invalid("required catalog producer observation is missing or duplicated")
    return sorted(receipts, key=lambda item: (item["kind"], item["path"])), records, captures


def _checks(
    supplied: object,
    *,
    requirements: Mapping[str, Requirement],
    spec: CaseSpec,
) -> list[dict[str, object]]:
    if not isinstance(supplied, list) or len(supplied) != len(requirements):
        _invalid("required catalog check is missing or duplicated")
    checks: dict[str, dict[str, object]] = {}
    for item in supplied:
        check = _object(item, frozenset({"id", "evidence"}))
        check_id = str(check.get("id") or "")
        requirement = requirements.get(check_id)
        if requirement is None or check_id in checks:
            _invalid("required catalog check is missing, unknown, or duplicated")
        evidence = check.get("evidence")
        expected = {requirement.kind}
        if requirement.kind.endswith("_observation"):
            expected.add(requirement.kind.replace("_observation", "_capture"))
        if (
            not isinstance(evidence, list)
            or any(not isinstance(value, str) for value in evidence)
            or len(evidence) != len(expected)
            or set(evidence) != expected
        ):
            _invalid("required catalog check is not bound to its exact producer or visible capture")
        checks[check_id] = {"id": check_id, "evidence": sorted(expected)}
    if set(checks) != set(requirements):
        _invalid("required catalog check is missing or duplicated")
    del spec
    return [checks[check_id] for check_id in sorted(checks)]


def _semantic_observations(
    records: Mapping[str, Mapping[str, object]],
    *,
    spec: CaseSpec,
    authority: LiveAuthority,
    captures: Mapping[str, Mapping[str, object]],
) -> None:
    identity = records["installed-runtime-identity"]["facts"]
    if (
        not isinstance(identity, dict)
        or identity.get("candidateDigest") != authority.candidate_digest
        or identity.get("artifactDigest") != authority.artifact_digest
        or identity.get("ownerRefHash") != authority.owner_ref_hash
        or type(identity.get("activeProcessCount")) is not int
        or int(identity["activeProcessCount"]) < 1
    ):
        _invalid("catalog installed artifact identity does not match the live owner")
    for surface in spec.capture_surfaces:
        observation = records[f"visible-installed-{surface}-user-path"]["facts"]
        capture = captures.get(surface)
        if (
            not isinstance(observation, dict)
            or not isinstance(capture, Mapping)
            or observation.get("captureSha256") != capture.get("sha256")
            or SHA256.fullmatch(str(observation.get("sourceRecordRefHash") or "")) is None
        ):
            _invalid("catalog visible or audible user capture is not producer bound")
        if surface == "voice":
            if observation.get("audibleFrameCount") != capture.get("frames"):
                _invalid("catalog audible Voice capture does not match its observation")
        elif (
            observation.get("viewportHeight") != capture.get("height")
            or observation.get("viewportWidth") != capture.get("width")
        ):
            _invalid("catalog visible user capture does not match its observation")
    if spec.restart_required:
        restart = records["restart-exact-process-recovery"]["facts"]
        if not isinstance(restart, dict):
            _invalid("catalog restart producer evidence is invalid")
        before = _hash(restart.get("beforeProcessRefHash"))
        after = _hash(restart.get("afterProcessRefHash"))
        before_at = _timestamp(restart.get("beforeAt"))
        after_at = _timestamp(restart.get("afterAt"))
        if (
            before == after
            or not authority.session_started_at <= before_at < after_at < authority.session_expires_at
            or type(restart.get("restoredRecordCount")) is not int
            or int(restart["restoredRecordCount"]) < 1
            or restart.get("duplicateEffectCount") != 0
        ):
            _invalid("catalog exact-process restart recovery is invalid or duplicated")


def _derived_digest(result: Mapping[str, object]) -> str:
    return _digest(
        {
            "artifactDigest": result.get("artifactDigest"),
            "candidateDigest": result.get("candidateDigest"),
            "caseId": result.get("caseId"),
            "checkCount": result.get("checkCount"),
            "checks": result.get("checks"),
            "contractVersion": result.get("contractVersion"),
            "evidence": result.get("_receiptEvidence"),
            "evidenceDigest": result.get("evidenceDigest"),
            "ownerRefHash": result.get("ownerRefHash"),
            "runAt": result.get("runAt"),
            "status": result.get("status"),
            "surface": result.get("surface"),
        }
    )


def assess_manifest(
    manifest: object,
    *,
    evidence_root: Path,
    expected_candidate_digest: str,
    expected_artifact_digest: str,
    installed_owner_proven: bool,
    now: datetime | None = None,
) -> dict[str, object]:
    """Derive PASS only from live signed records and the exact real user surfaces."""

    if installed_owner_proven is not True:
        _invalid("catalog active installed-runtime owner identity is not proven")
    payload = _object(manifest, MANIFEST_FIELDS)
    case_id = str(payload.get("caseId") or "")
    spec = CASE_SPECS.get(case_id)
    if (
        spec is None
        or payload.get("contractVersion") != CONTRACT_VERSION
        or payload.get("schema") != MANIFEST_SCHEMA
        or payload.get("environment") != "installed_local_production"
    ):
        _invalid("catalog installed case, environment, or contract is invalid")
    candidate = _object(payload.get("candidate"), frozenset({"candidateDigest", "artifactDigest"}))
    expected_candidate = _hash(expected_candidate_digest)
    expected_artifact = _hash(expected_artifact_digest)
    if (
        candidate.get("candidateDigest") != expected_candidate
        or candidate.get("artifactDigest") != expected_artifact
    ):
        _invalid("catalog candidate or installed artifact does not match")
    correlation = _object(
        payload.get("correlation"), frozenset({"ownerRefHash", "sessionRef", "surface"})
    )
    owner = _hash(correlation.get("ownerRefHash"))
    session_ref = str(correlation.get("sessionRef") or "")
    if correlation.get("surface") != spec.surface:
        _invalid("catalog user surface does not match the exact case")
    checked = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    run_at = _timestamp(payload.get("runAt"))
    if run_at > checked + MAX_FUTURE_SKEW or checked - run_at > MAX_RESULT_AGE:
        _invalid("catalog installed producer evidence is stale or in the future")
    requirements = {item.id: item for item in case_requirements(case_id)}
    checks = _checks(payload.get("checks"), requirements=requirements, spec=spec)
    root = _private_root(evidence_root)
    authority = _authority(
        probe_live_authority(
            case_id=case_id,
            owner_ref_hash=owner,
            session_ref=session_ref,
            evidence_root=root,
            evidence=payload.get("evidence"),
            now=checked,
        ),
        case_id=case_id,
        candidate=expected_candidate,
        artifact=expected_artifact,
        owner=owner,
        session_ref=session_ref,
        run_at=run_at,
        now=checked,
    )
    receipts, records, captures = _verified_evidence(
        payload.get("evidence"),
        root=root,
        case_id=case_id,
        spec=spec,
        requirements=requirements,
        owner=owner,
        authority=authority,
        run_at=run_at,
    )
    _semantic_observations(records, spec=spec, authority=authority, captures=captures)
    result: dict[str, object] = {
        "_receiptEvidence": receipts,
        "artifactDigest": expected_artifact,
        "candidateDigest": expected_candidate,
        "caseId": case_id,
        "checkCount": len(checks),
        "checks": checks,
        "contractVersion": CONTRACT_VERSION,
        "evidenceDigest": _digest(receipts),
        "ownerRefHash": owner,
        "runAt": run_at.isoformat(timespec="milliseconds"),
        "status": "PASS",
        "surface": spec.surface,
    }
    digest = _derived_digest(result)
    seal = hmac.new(_DERIVATION_KEY, digest.encode("utf-8"), hashlib.sha256).hexdigest()
    result["_derivationDigest"] = digest
    result["_derivationSeal"] = seal
    result["_derivedPass"] = _DERIVED_PASS
    if len(_ISSUED_PASSES) >= 256:
        _ISSUED_PASSES.pop(next(iter(_ISSUED_PASSES)))
    _ISSUED_PASSES[id(result)] = (result, digest, seal)
    return result


def receipt_manifest(*, result: dict[str, object]) -> dict[str, object]:
    """Return the writer's strict manifest only for this process's genuine result."""

    if not isinstance(result, dict):
        _invalid("catalog derived PASS is invalid")
    issued = _ISSUED_PASSES.get(id(result))
    try:
        digest = _derived_digest(result)
    except (TypeError, ValueError):
        _invalid("catalog derived PASS is invalid")
    seal = hmac.new(_DERIVATION_KEY, digest.encode("utf-8"), hashlib.sha256).hexdigest()
    case_id = str(result.get("caseId") or "")
    spec = CASE_SPECS.get(case_id)
    evidence = result.get("_receiptEvidence")
    if (
        issued is None
        or issued[0] is not result
        or result.get("_derivedPass") is not _DERIVED_PASS
        or not hmac.compare_digest(str(result.get("_derivationDigest") or ""), digest)
        or not hmac.compare_digest(digest, issued[1])
        or not hmac.compare_digest(str(result.get("_derivationSeal") or ""), issued[2])
        or not hmac.compare_digest(issued[2], seal)
        or spec is None
        or result.get("contractVersion") != CONTRACT_VERSION
        or result.get("status") != "PASS"
        or result.get("surface") != spec.surface
        or result.get("checkCount") != len(case_requirements(case_id))
        or not isinstance(evidence, list)
        or not evidence
        or evidence != sorted(evidence, key=lambda item: (item["kind"], item["path"]))
    ):
        _invalid("catalog derived PASS is invalid")
    return {
        "caseId": case_id,
        "contractVersion": CONTRACT_VERSION,
        "evidence": evidence,
        "runAt": _timestamp(result.get("runAt")).isoformat(timespec="milliseconds"),
        "status": "PASS",
        "surface": spec.surface,
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--case-id", required=True, choices=sorted(CASE_SPECS))
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--evidence-root", required=True, type=Path)
    parser.add_argument("--artifact-identity", required=True, type=Path)
    arguments = parser.parse_args(argv)
    try:
        root = _private_root(arguments.evidence_root)
        supplied = arguments.manifest.expanduser().resolve(strict=True)
        relative = supplied.relative_to(root).as_posix()
        raw, _path = _private_file(relative, root=root)
        manifest = _strict_json(raw)
        if not isinstance(manifest, dict) or manifest.get("caseId") != arguments.case_id:
            _invalid("catalog manifest does not belong to the selected case")
        gate = _load_module(
            Path(__file__).resolve().parents[3] / "scripts/viventium/parallel_work_release_gate.py",
            "viventium_catalog_cli_release_gate",
        )
        identity_raw = arguments.artifact_identity.read_bytes()
        if len(identity_raw) > MAX_FILE_BYTES:
            _invalid("catalog installed artifact identity is invalid")
        candidate, artifact = gate._qa_candidate_digests(_strict_json(identity_raw))
        result = assess_manifest(
            manifest,
            evidence_root=root,
            expected_candidate_digest=candidate,
            expected_artifact_digest=artifact,
            installed_owner_proven=True,
        )
        print(_canonical({key: value for key, value in result.items() if not key.startswith("_")}))
        return 0
    except (OSError, RuntimeError, TypeError, ValueError):
        print(_canonical({"caseId": arguments.case_id, "status": "BLOCKED"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

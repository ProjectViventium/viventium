# Local-Prod GlassHive Cold-Start Readiness — 2026-08-12

## Outcome

PARTIAL pending the post-fix transactional activation. A legitimate GlassHive candidate with existing persisted
state may take longer than three seconds to expose runtime health. The launcher now polls the
runtime, MCP, and UI surfaces for a bounded interval, fails immediately when a candidate process
exits, and tears down only the candidate when readiness cannot be reached.

## Evidence

- The pre-fix transactional activation reached all other validation gates, then rolled back because
  its one readiness check ran after a fixed three-second sleep.
- An isolated fresh-state probe reached complete readiness in 0.58–0.98 seconds.
- A production-shaped 203 MB SQLite state copy kept all three candidate processes alive at 3.015
  seconds and reached complete runtime/MCP/UI readiness at 4.634 seconds. Candidate ports were free;
  no stale process, dependency sync, or resource-exhaustion explanation matched the evidence.
- The focused launcher regression verifies a 30-second default, a 120-second maximum, all three PID
  fail-fast checks, repeated readiness probes, and removal of the fixed three-second gate.
- The post-fix supported transactional `dev-runtime activate-current --validate --restart` remains
  the final acceptance gate; this report must be updated with its receipt and provenance result.

No private state contents, credentials, local user paths, hostnames, or personal runtime data are
included in this report.

## Remaining Product Gates

This result proves local activation readiness. It does not replace Telegram answer-quality QA,
credentialed connected-account and health checks, audible voice QA, or the broader release matrix.

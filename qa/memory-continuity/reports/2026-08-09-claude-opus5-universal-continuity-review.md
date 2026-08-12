<!-- qa-evidence-exempt: Sanitized review-only evidence; no private prompt, identifiers, paths, logs, screenshots, or runtime payloads. -->

# Claude Opus 5 universal continuity review — 2026-08-09

## Review contract

- Mode: Claude Desktop, existing isolated project session, Opus 5, Extra effort, review-only.
- Requested decision: challenge the evidence-backed RCA, structural fix, tests, QA claims, and
  remaining limitations; do not modify files.
- Evidence supplied: requirements and architecture, owning code, frozen eval definitions/results,
  scheduler/runtime evidence, broker/auth boundaries, saved-memory/recall paths, browser/Telegram/
  voice QA summaries, and the universal acceptance report.
- Alternative explanations considered before review: one missing entity only; same-thread context
  mistaken for memory; `/host` connectivity mistaken for user OAuth; stale credentials mistaken for
  usable provider access; successful-empty recall mistaken for provider failure.

## Findings and disposition

Claude initially returned `APPROVE WITH CONDITIONS`, then inspected the current files and found:

1. schema-v2 scheduler compatibility could reopen after receipt pruning;
2. LaunchAgent execution used environment-sensitive command resolution;
3. the architecture diagram overstated a bearer grant as stronger per-turn authentication;
4. the tool-ownership case sat outside the frozen continuity fingerprint;
5. main and background model fallback provenance needed an honest visible boundary.

The implementation was revised and re-reviewed:

- a durable schema-v3 observation marker outside the prunable receipt directory permanently closes
  legacy acceptance, including reader migration and fail-closed persistence behavior;
- LaunchAgent generation pins the resolved interpreter and `/bin/launchctl`, with installed-artifact
  verification;
- documentation now says “signed turn-context-scoped bearer grant” and states the local-operator
  attestation ceiling;
- the frozen bank is `continuity-recall-v1.1.0` / `987dfffc5021ba69`, with 12 fingerprinted
  categories including tool ownership;
- main-agent and background-cortex fallback results persist structural provenance and expose
  public-safe expandable disclosures;
- a final disposable non-admin browser run proved real background-cortex activation, a deliberately
  unavailable primary, configured fallback insight, expanded disclosure, reload persistence,
  persisted-field agreement, zero console errors, and exact fixture cleanup.

Claude inspected the final harness and report, found a strict eight-gate pass plus cleanup gate,
low false-positive risk, exact structural/UI checks, and no production entity or prompt rule. It
also identified that the first fixture depended on Anthropic remaining disconnected. The harness
was changed to a disposable guaranteed-unavailable synthetic primary, rerun successfully, and no
longer conflicts with the pending Anthropic reconnect.

## Final verdict

**APPROVE — no blockers for the scoped tested-local-path continuity statement.**

Claude independently reproduced the scheduler/prompt slice (133 passing) and the final background
fallback suites (43/43 backend and 13/13 client with Jest pinned to the workspace-compatible
version). Review-only scope did not execute the installed runtime or browser harness; Codex supplied
that separate user-path evidence.

Claude agreed this statement is supportable:

> For the tested local paths, the main agent receives authorized bounded saved memory, recall,
> provider/account state, and declared tools; missing evidence/auth is explicit. It is not
> omniscient, release-ready, or fully proven for untested paths.

## Remaining disclosed risks

- Emotional-reaction fallback remains structurally observable but has no user-visible disclosure;
  it changes feeling state rather than presenting a result, so it is excluded from any blanket
  “no silent fallback” claim.
- Scheduler receipts are local-process attestations, not cryptographic proof; a kickstart within the
  calendar jitter window cannot be distinguished from natural OS cadence at this layer. The next
  natural schema-v3 receipt remains the cadence-transition gate.
- Memory rename is compare-and-swap/tombstone safe but not transactional across every crash point; a
  mid-sequence crash can leave a non-destructive recoverable duplicate.
- The broker is intentionally bearer-authenticated. Signed turn fields are presence-checked, not
  independently compared with a second caller identity; pre-auth abuse limiting remains separate
  from grant-scoped post-auth limiting.
- World-memory compaction currently removes URL/email-shaped text, so ordinary notes containing
  those values can lose content during compaction.
- The nested LibreChat changes remain uncommitted and the parent component pin/release artifact has
  not been advanced.
- Test Account Anthropic still requires reconnect; 13 protected live Agent Builder differences
  remain intentionally unsynced pending explicit reconciliation.

No files were modified by Claude.

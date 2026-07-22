# Fable 5 Extra Review — 2026-07-18

## Review Boundary

This is the public-safe reconciliation record for an independent, review-only Fable 5 pass at Extra
effort. The reviewer received the original user request verbatim, the audit evidence bundle, the
provisional findings, the relevant owning files, and alternative explanations already considered.
It was told not to edit files or mutate runtime, account, database, or cloud state.

The review inspected nine supplied files, ran seventeen read-only repository queries, and used four
internal research/review passes. A requested duplicate full release-suite run was intentionally not
approved because the primary audit had already run it and the review boundary was read-only.

Verdict: **FAIL.** The Express/public-release claim does not pass. The review independently validated the core
installer, continuity, readiness, bootstrap, onboarding, delivery-drift, and clean-Mac evidence gaps.

## Corrections Incorporated

### Continuity is a contract defect, with a more severe history risk

- Metadata-only fallback is explicitly allowed by the installer requirement,
  `qa/continuity-ops/`, and `test_continuity_audit.py`; it is not merely an accidental code
  regression.
- The fallback can reuse the latest snapshot directory and rewrite its manifest. A later
  metadata-only attempt can therefore collapse history and replace the manifest for a real
  snapshot, weakening restore-age and safety gates.
- Remediation must update requirement, continuity contract, implementation, helper/CLI wording,
  and test together. Repeated-fallback preservation is now an explicit regression case.

### Configure has a reusable safe-write precedent

- Interactive configure, recovery reconfigure, and especially `--config-input` bypass complete
  candidate/merge/backup/rollback semantics.
- `scripts/viventium/config_settings.py` already contains a backup, temporary-file, and atomic
  `os.replace` pattern. The implementation plan now calls for reusing that primitive.

### Easy and provider prerequisites need more precise wording

- Interactive Easy asks beyond Groq and optional Telegram. Voice is hardware-gated, and browser
  account authentication is separately gated.
- The code contains an Easy-specific web-search branch that the current caller does not use,
  indicating implementation drift from the intended contract.
- Interactive setup always asks for Groq, but preset/headless behavior can select an xAI activation
  override or omit GlassHive. The audit now distinguishes those paths.
- A credential reference or provider name can currently look configured even when the referenced
  secret is dangling or no usable key exists. No live provider request proves `Ready`.

### Bootstrap defects and future release hardening are separate

- Mutating any existing `.git` destination without validating its Viventium origin is the immediate
  safety defect.
- Signed/versioned bootstrap, SBOM, and provenance are documented future release scope. They remain
  required for a secure release boundary, but are no longer presented as the same current
  regression.

### Feelings is a requested feature gap, not a failure against the current requirement

- The owning document is `54_Emotional_Cortex_And_Feeling_State.md`; it currently specifies the
  account-menu entry, not the requested right-side control-panel entry.
- The requirement must change before implementation. The recommended LibreChat change is a
  navigation action to `/feelings`, gated by the existing default-on startup availability flag.
- A clean worktree from the delivery pin is required. Target navigation files were clean during
  audit, while adjacent Feelings feature files had unpublished edits.
- The nested change must use Viventium fork markers, repair adjacent unwrapped Feelings additions,
  run browser QA on the built artifact, then preserve nested commit → parent pin → built/installed
  artifact alignment.

### QA and history records needed reconciliation

- The two release-suite failures come from pre-existing untracked working-tree reports. They prove
  current working-tree drift, not by themselves a committed release regression. The recurring
  report-generation workflow needs its own traced fix.
- The readiness registry has three dangling owner references: generic GlassHive, connected
  accounts, and Code Interpreter.
- The lifecycle command used two incorrect QA paths. The corrected paths are
  `qa/installer-piped-bootstrap/` and `qa/installer-wait-taglines/`, and commit `26251bd` belongs in
  the ledger.
- Umbrella installer cases now cross-reference continuity, piped bootstrap, Telegram, and MCP/OAuth
  owners rather than silently replacing them.
- Current case results now distinguish what ran in this audit from historical results:
  `INST-001` partial, this audit's `INST-002` pass with separate working-tree failure,
  `INST-003` not rerun, and current `INST-004` fail.

## Additional Matrix Cases Added

The remediation and case catalog now explicitly cover:

- Gatekeeper, notarization, quarantine, and first-launch permissions;
- forgotten local password without SMTP, a second local user, and multiple local accounts;
- cross-machine restore and schema downgrade/forward-migration refusal;
- Safari/default-browser handoff, non-English macOS, terminal accessibility, and reduced motion;
- laptop sleep, concurrent double install/locking, and upgrade while a schedule runs;
- day-two disk exhaustion, MDM/no-admin environments, and recurring QA-report generation safety.

## Recommended Execution Order

1. Start disposable Apple Silicon macOS VM procurement immediately.
2. Freeze claims and reconcile normative contracts and QA ownership.
3. Land narrow truth/safety fixes: backup wording, immutable fallback attempts, Easy copy,
   destination-origin validation, and `--config-input` safety.
4. Build full restore, then transactional configure.
5. Add bootstrap journaling and keep release signing/provenance on its documented boundary.
6. Build minimal account-first onboarding and shared connection health.
7. Run the Feelings requirement/navigation slice in parallel from a clean delivery-pin worktree.
8. Complete Telegram onboarding, then fresh-Mac and restored-existing-user acceptance.
9. Keep Slack and WhatsApp as separately approved roadmap work.

Fresh-Mac QA does not depend on personal-state recovery work and can start when the VM exists.
Destructive existing-user QA remains gated on verified backup/restore and transactional configure.

## Independent-Review Limitation

This review is supporting evidence. It does not replace the blocked clean-Mac installer run, exact
public artifact, real first account/provider/answer, live integrations, restart persistence, full
browser-visible restore, or user-grade voice proof.

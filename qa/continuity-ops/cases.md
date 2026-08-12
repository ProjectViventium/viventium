# Continuity Ops QA Cases

## Case ID Convention

Use stable `CONT-NNN` IDs for continuity ops cases.

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `CONT-001` | Backup, restore, upgrade, and continuity checks keep user data recoverable across runtime changes. | User-visible behavior matches source, docs, persisted state, and logs | CLI/helper, snapshots, restore markers, runtime status | `tests/release/test_continuity_audit.py` plus user-grade QA when visible | PARTIAL 2026-07-19; metadata-only/invalid/private-helper refusal, no-mutation validation, upgrade continuity gates, full-tree preserve-data uninstall, and manual supporting recovery ran. Public capture/apply and independent-target browser recovery remain open |
| `CONT-002` | Public QA evidence is sanitized and reproducible | A PR reviewer can verify the behavior without private/local data | QA report, git diff, logs summary, generated artifacts | Public-safety scan plus relevant release tests | PASS 2026-07-19; final public-safety test and explicit private-path/identity/connection scan passed after the report update; raw evidence stays outside the repo |
| `CONT-003` | Metadata-only fallback never mutates a prior snapshot, becomes a restore source, or is presented as a recoverable backup. | Failed or unavailable payload capture cannot destroy recovery history or give false safety. | CLI/helper, `LATEST_PATH`, attempt marker, manifests, restore | Snapshot/restore fallback regressions plus helper wording contract | PASS 2026-07-19; synthetic prior snapshot stayed unchanged, failed capture preserved the atomic pointer, invalid marker-less private-helper output was not published, helper wording distinguishes complete/metadata/invalid proof, and restore rejected non-payload selections before creating state |
| `CONT-004` | Restore accepts only a positive, complete, content-verified candidate and never calls structural validation a complete restore. | An arbitrary/corrupt directory cannot mutate a new target or give false recovery confidence. | bundle validator, restore CLI, independent target, domain/artifact manifest | `tests/release/test_continuity_bundle.py` and `test_continuity_audit.py` | PARTIAL 2026-07-19; focused regressions pass for positive producer marker/schema/domain/hash/bounded-content/path validation, standard-library-only execution, source/target overlap refusal, explicit `recoverable: false`, and nonzero no-mutation apply refusal. Complete capture/apply, Mongo semantic proof, and browser-visible recovery remain open |

## `CONT-003` - Immutable Metadata-Only Fallback

- Preconditions: a synthetic prior snapshot with a sentinel manifest, plus private-helper absent and
  private-helper-success-without-new-path variants.
- Steps:
  1. Run the public snapshot wrapper twice against the same output root.
  2. Repeat with a synthetic private helper that exits successfully without recording a new path.
  3. Inject a manifest-capture failure and confirm `LATEST_PATH` still names the prior good snapshot.
  4. Compare the prior directory and manifest before/after.
  5. Inspect the new attempt marker, atomic `LATEST_PATH`, CLI warning, and helper success wording.
  6. Invoke restore through `LATEST_PATH` and an explicit path; confirm both fail before a live audit
     or restore-side state is created.
- Expected result: every fallback creates a distinct metadata-only attempt, prior snapshots remain
  unchanged, the user is told that no recoverable backup payload was created, and restore refuses
  to treat the attempt as payload.
- Forbidden result: latest prior manifest rewritten, history collapsed, metadata called a backup,
  a no-op private helper treated as a new payload snapshot, or default/explicit restore continuing
  against a metadata-only directory.
- Evidence to capture: prior/new paths, manifest hashes, marker, sanitized CLI/helper wording, and
  focused test output.
- Last run: PASS 2026-07-18 through synthetic wrapper, manifest-failure, restore-refusal, and helper
  source-contract tests, extended 2026-07-19 with positive marker-less refusal. Full browser-visible
  payload restore remains separately blocked.

## `CONT-001` - Core User Flow

- Requirement: Backup, restore, upgrade, and continuity checks keep user data recoverable across runtime changes.
- Risk covered: implementation, docs, and user-visible behavior drift apart.
- Preconditions: local Viventium runtime or the specific feature harness is available with synthetic, public-safe data.
- Steps:
  1. Exercise the feature through the real user surface, not only a unit test.
  2. Compare the visible result with source code, generated/runtime config, logs, persisted state, and the owning requirement doc.
  3. Capture a public-safe report with expected result, forbidden result, evidence, residual risk, and follow-up.
- Expected result: the feature behaves as documented and every supporting layer agrees.
- Forbidden result: backend logs, mocks, source inspection, or model completions are treated as full acceptance when a user-visible surface exists.
- Evidence to capture: sanitized visible result, supporting command/test result, generated/runtime state summary, and docs/case links.
- Automation: `tests/release/test_continuity_audit.py` plus any narrower feature tests discovered during implementation.
- Last run: PARTIAL 2026-07-19. Real CLI/helper/VM continuity-adjacent paths and supporting state
  were inspected, but the deliberately disabled public apply path and missing independent-target browser restore keep
  this case open.

## `CONT-002` - Public-Safe Evidence Record

- Requirement: public QA artifacts must be reproducible and free of secrets, personal data, local paths, raw IDs, and private screenshots.
- Risk covered: a useful local QA run cannot be safely reviewed or published.
- Preconditions: a dated QA report is created for this feature.
- Steps:
  1. Review the report and related diffs for local absolute paths, account identifiers, tokens, raw logs, raw DB rows, private chats, and screenshots with private content.
  2. Keep raw/private evidence outside the public repo and summarize only public-safe counts, statuses, hashes, and conclusions.
  3. Link the report back to this case and the owning requirement doc.
- Expected result: the public report proves the behavior without leaking private/local data.
- Forbidden result: a report includes private transcripts, account identifiers, raw runtime dumps, local home paths, tokens, or secret-bearing command lines.
- Evidence to capture: public-safety scan result and link to the sanitized report.
- Automation: public-safety pattern scan plus relevant release tests.
- Last run: PASS 2026-07-19. The dated installer report and owning QA/docs were scanned after the
  final changes; no personal path, identity, connection handoff, secret, or staged file was found.

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Continuity Ops. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `CONT-UC-001` | On CLI/helper, snapshots, restore markers, runtime status, verify that backup, restore, upgrade, and continuity checks keep user data recoverable across runtime changes. | owning requirement for `CONT-001` / `CONT-001` | CLI/helper, snapshots, restore markers, runtime status | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to CONT-001. | User-visible behavior matches source, docs, persisted state, and logs | PARTIAL 2026-07-19; tested refusal/preservation/recovery/upgrade gates agree with source and state, but public independent recovery is absent |
| `CONT-UC-002` | On QA report, git diff, logs summary, generated artifacts, create or review the public QA evidence record with setup/auth/config, empty-state, degraded-dependency, and privacy checks. | owning requirement for `CONT-002` / `CONT-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to CONT-002. | The user sees an honest setup, retry, or degraded-state result for CONT-002; no fake success is accepted. | PASS 2026-07-19; report explicitly separates structural validation, manual recovery, and missing public restore, and public-safety checks pass |
| `CONT-UC-003` | After creating the public QA evidence record, rerun the scan after any retry, report update, or linked artifact change. | owning requirement for `CONT-002` / `CONT-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to CONT-002. | CONT-002 remains correct after the persistence or parity step and final wording matches evidence. | PASS 2026-07-19; final post-update scans found zero private-path/identity/connection hits and zero staged files |

## Release Test Traceability

- `tests/release/test_continuity_audit.py`
- `tests/release/test_continuity_bundle.py`

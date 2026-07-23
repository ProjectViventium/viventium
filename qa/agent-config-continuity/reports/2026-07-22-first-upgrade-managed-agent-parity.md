# First-Upgrade Managed-Agent Parity QA — 2026-07-22

## Summary

Status: PARTIAL

The supported source-upgrade path now carries the exact prior LibreChat release into the first
baseline-aware seed without trusting ambient environment state. Automated evidence covers every
retrievable public pin from the reviewed support floor, the exact previously shipped CLI process,
interruption/rollback/retry, unchanged-field advancement, synthetic user-edit preservation, and
one-time consumption. A real established-user browser and database upgrade was not run in this pass.

## Scope Run

- Audited all 74 public parent lock revisions from the April 2, 2026 support floor.
- Re-resolved 62 retrievable LibreChat pins into 22 managed-baseline groups.
- Verified the three unretrievable lock entries are explicit never-published tombstones.
- Ran an actual synthetic old CLI process across a parent fast-forward and nested component update,
  then started the new code from the resulting installed state.
- Exercised protected handoff creation, exact retry, stale/different/tampered rejection, transaction
  rollback, markerless discovery from the shipped CLI's verified upgrade ledger, legacy-marker
  compatibility, and durable one-time consumption with a private transaction receipt.
- Verified byte-exact regeneration at the recorded parent lock-history boundary and a synthetic
  later parent pin that does not force a self-referential nested artifact rewrite.
- Verified background-agent runtime repair preserves a synthetic model-parameter edit.
- Verified native payload assembly still includes and accepts the migration registry.

## Traceability

`docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md` -> `AGCFG-007` ->
`AGCFG-UC-007` -> source upgrade CLI / startup seed -> protected App Support state, component refs,
registry and bundle hashes -> automated evidence below -> remaining real browser/DB upgrade gap.

## Full-View Evidence Checklist

- Feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining
  gap: connected above.
- Real user path: not run; this result remains PARTIAL.
- Docs and nested docs: owning installer requirement and agent-continuity QA contract updated.
- Logs, DB/state/persistence: synthetic upgrade transaction, protected pending state and import
  receipt, baseline reconciliation, and one-time removal inspected by tests; no live personal
  database used.
- Generated/shipped artifact verification: standalone registry audit and native payload assembly pass.
- Public/private safety: fixtures use synthetic identities and temporary paths; the tracked artifact
  contains hashes and public commit identities, not prompts, credentials, or machine-local state.

## User-Grade Evidence

- Surface exercised: supported CLI upgrade/start behavior in isolated synthetic repositories.
- Real user path: NOT RUN in an established user's browser or live database.
- Visible outcome: CLI process success and fail-closed messages are asserted; no browser screenshot
  is claimed.
- Expanded/detail state: predecessor, successor, bundle, registry, transaction, and content bindings
  are asserted in protected state.
- Persistence/reload result: exact retry succeeds, a second upgrade is refused while migration is
  pending, rollback restores absence, and successful seed-style reconciliation removes the record.
- Backend/log/DB confirmation: deterministic reconciliation confirms prior-unchanged advancement and
  synthetic edit preservation; a live MongoDB record was not used.
- Final model/runtime wording check: no model completion was used as acceptance evidence.
- Substitution check: source, state, transaction, artifact, and automated evidence support this
  result but do not replace the unrun established-user browser and database upgrade path.

## Automated Evidence

- `tests/release/test_cli_upgrade.py`: 77 passed.
- LibreChat `api/test/scripts/viventium-seed-agents.test.js`: 30 passed in the final focused rerun.
- Migration-state, standalone/full-history, native payload, and QA-contract group: 124 passed
  (10 migration-state, 3 history, 85 native-payload, and 26 QA-contract).
- Final release-gate rerun: the full parent release suite passed 1,560 with 30 expected skips; the
  exact shipped-CLI process case passed; generator output matched the tracked registry byte for byte.
- The standalone nested API lane re-audited all 62 predecessor objects from complete Git history in
  hosted CI; all 14 LibreChat PR 71 checks passed before merge to
  `9e859bcac6a691bb67224380842b44b96a6e3073`, and the parent lock/payload policies pin that merge.
- Shell syntax checks passed for the public CLI and source launcher.
- Prettier checks passed for the affected nested JavaScript files.

## Findings

- The new CLI creates a mode-`0600` state record after candidate validation and binds it to both
  source refs, the successor bundle, migration registry, and immutable transaction.
- The exact previously shipped CLI remains compatible even though it writes no migration marker: new
  startup derives the predecessor only when its runner-hash-verified ledger proves the same nested
  transition. The legacy generated-runtime marker remains supported, and a mode-`0600`
  per-transaction receipt prevents either path from being replayed after successful consumption.
- Pending state is reused only for the exact same transaction and content. Different or tampered
  evidence fails closed without replacing the existing record.
- The nested `--check` path works without an adjacent parent checkout and validates all 62 objects;
  full history regeneration requires an explicit exact parent root and audits through the artifact's
  frozen last-lock boundary rather than moving branch HEAD.
- No automated failure remains in the scoped source-upgrade parity work. The remaining gap is a real
  established-user browser/DB upgrade, which supporting evidence cannot replace.

## Public-Safety Review

The report contains only public commit counts, synthetic behavior, relative project paths, and test
results. It contains no personal identity, local home path, credential, account identifier,
conversation content, raw database row, private prompt, screenshot, or runtime dump.

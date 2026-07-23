# Agent Config Continuity QA

## Scope

Verify that built-in Viventium agents do not lose live user-managed settings during startup reseed,
restore, or normal local restart flows.

Covered surfaces:

1. live user-level agent snapshot restore
2. built-in startup reseed behavior for existing agents
3. restart survival for main-agent and background-agent model config
4. live Agent Builder UI truth after restart

## Requirements Under Test

- Existing built-in agents must preserve live user-managed fields during startup reseed.
- A first upgrade with no local managed baseline must use only the exact, hash-verified prior
  shipped baseline registered for the captured pre-pull LibreChat commit. It must advance unchanged
  shipped fields, preserve real user edits, and reject unknown or tampered predecessor evidence.
- The supported public history audit covers all 74 lock revisions from the reviewed support floor:
  62 retrievable LibreChat pins in 22 resolved baseline groups plus three explicit never-published
  tombstones. Its nested-checkout verification must not require an adjacent parent repository, and
  its parent audit must stop at the registry's recorded history boundary so a later release pin does
  not create a self-referential nested/parent publication loop.
- Upgrade identity crosses the compile/start boundary only in a durable owner-only one-time App
  Support record bound to predecessor, successor, bundle, registry, and transaction. Exact retries
  are idempotent; different or tampered pending state fails closed; successful seed consumes it only
  after agent, ACL, and baseline writes finish.
- A first upgrade launched by a previously shipped CLI that predates that handoff must recover the
  predecessor only from its owner-only, runner-hash-verified upgrade ledger. A private per-transaction
  receipt prevents the discovered migration from being recreated after successful consumption.
- Startup reseed may create missing built-ins, fill missing fields, and repair runtime-only state,
  but must not overwrite live user-managed agent fields on existing installs.
- Runtime-only canonical repair must consume the effective reconciled assignment and must not undo
  protected model, tools, voice, prompt, or other managed drift.
- The first verified administrator becomes the durable canonical built-in-agent owner. Native and
  source starts must verify that exact stored ID after additional administrators exist, never infer
  from query ordering, and fail closed with recovery guidance if protected owner state is invalid.
- The installed checkout used by the running stack must match the intended seed-script fix; a
  source-only patch does not pass QA.
- A live restore from a last-known-good user snapshot must survive at least one fresh local stack
  restart.
- Live Agent Builder UI after restart must agree with the pulled live bundle for the restored
  agent fields.

## Environments

- public repo checkout
- installed local Viventium checkout used by the running app
- live local Viventium stack with Agent Builder UI
- public-safe live agent bundle snapshots only

## Test Cases

1. Compare live bundle against last-known-good user snapshot after restore
2. Patch tracked and installed `viventium-seed-agents.js` to preserve live user-managed fields for
   existing built-in agents
3. Run the owning seed-script test path in both tracked and installed checkouts
4. Restart the full local stack so the installed seed path runs again
5. Pull a fresh live bundle after restart and compare it with the restored-good snapshot
6. Refresh Agent Builder and verify the restored model, voice model, and instructions in the live
   UI
7. Remove the synthetic local baseline, capture a registered predecessor commit, and verify a first
   upgrade advances prior-unchanged fields while preserving synthetic edits in update and repair
8. Repeat with an unknown predecessor, a tampered local baseline, and a tampered migration registry;
   verify each case fails closed without advancing the managed baseline
9. Assemble the native payload and verify the managed-baseline migration registry is present and
   accepted by the installed seed loader without target-machine build tools
10. Add a second synthetic administrator, restart, and verify the stored owner ID, every built-in
    author/owner ACL, and baseline remain bound to the first verified administrator
11. Run the standalone nested migration audit, the explicit parent-history audit, exact pending-state
    retry/tamper tests, transaction rollback, and one-time successful consumption checks
12. Append a synthetic component-lock commit after the recorded audit boundary and verify the
    historical artifact remains byte-exact without regenerating the nested release

## Expected Results

- Restore re-establishes the intended live user config for the built-in main agent and reviewed
  background agents.
- Post-restart compare reports zero diffs for the reviewed live bundle versus the restored-good
  snapshot.
- The live Agent Builder panel shows the restored values rather than the stale installed seed
  values.
- Source tests and installed-checkout tests both pass for the owning seed script.
- The stored next baseline changes only after every agent/ACL operation succeeds.

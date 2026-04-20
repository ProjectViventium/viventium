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
- Startup reseed may create missing built-ins, fill missing fields, and repair runtime-only state,
  but must not overwrite live user-managed agent fields on existing installs.
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

## Expected Results

- Restore re-establishes the intended live user config for the built-in main agent and reviewed
  background agents.
- Post-restart compare reports zero diffs for the reviewed live bundle versus the restored-good
  snapshot.
- The live Agent Builder panel shows the restored values rather than the stale installed seed
  values.
- Source tests and installed-checkout tests both pass for the owning seed script.

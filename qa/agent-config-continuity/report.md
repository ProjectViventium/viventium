# Agent Config Continuity Report

Date: 2026-04-19
Status: pass

## Incident

Built-in agent settings reverted after local runtime startup. The visible regression affected the
main Viventium agent and removed restored user-managed values such as the current instructions,
main model, and voice-chat model.

## Root Cause

Startup reseed for built-in agents preserved too little live state on existing installs. The
existing path preserved background-cortex wiring but did not preserve the broader user-managed
fields for built-in agents. The runtime-field repair path also operated on the raw incoming seed
data instead of the merged preserved agent data. When the installed checkout carried an older
seed bundle, startup reseed rolled the live user config back to that older bundle.

## Fix Under Test

- Restore the live built-in agents from the last-known-good local user snapshot dated 2026-04-16
- Update the tracked and installed `viventium-seed-agents.js` path so existing built-in agents
  preserve live user-managed fields during reseed
- Pass the merged preserved agent data into runtime-field repair
- Add or update the owning seed-script tests to cover preserved instructions, model config, voice
  config, tools, and background-cortex wiring

## Evidence

### Restore verification

- A fresh pull taken immediately after restore matched the 2026-04-16 live snapshot for the
  reviewed built-in agent fields

### Owning automated checks

- Tracked source checkout:
  - `npm run test:ci -- --runTestsByPath test/scripts/viventium-seed-agents.test.js`
  - result: pass (`8` tests)
- Installed checkout used by the running app:
  - `npm run test:ci -- --runTestsByPath test/scripts/viventium-seed-agents.test.js`
  - result: pass (`6` tests)

### Restart-cycle proof

- Restarted the local stack through the supported start path so the installed seed script executed
  again
- Fresh live compare after restart:
  - reviewed live bundle vs restored-good 2026-04-16 snapshot
  - result: `diffCount: 0`

### Live UI proof

- Refreshed the live Agent Builder panel after restart
- Verified the main agent showed the restored values instead of the stale seeded values:
  - instructions begin with `You're Viv (Viventium)...`
  - main model is `claude-opus-4-7`
  - voice chat model is `claude-haiku-4-5`

## Verdict

The user-managed built-in agent config was restored successfully and survived a fresh local
restart. The fix is present in both tracked source and the installed checkout used by the running
stack, so the same rollback mechanism should not recur on normal restarts from the current
installation.

## Residual Risk

- If a future installed checkout drifts from the tracked repo again, startup behavior will follow
  the installed checkout unless the deployment/update flow refreshes it.
- Adjacent runtime toggles such as global web-search enablement remain separate from the agent
  bundle and should be reviewed independently when capability drift is reported.

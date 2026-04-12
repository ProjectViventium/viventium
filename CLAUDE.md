# Viventium Core

This is the proposed Claude-specific working file for Viventium Core. It stays lean on purpose and
pushes deep detail into the existing product docs instead of bloating the always-loaded context.

## Commands

```bash
# Public entrypoints
./install.sh
bin/viventium
viventium_v0_4/viventium-librechat-start.sh

# Release / installer / compiler checks
python3 -m pytest tests/release/ -q
python3 -m pytest tests/release/test_config_compiler.py -q

# LibreChat fork
cd viventium_v0_4/LibreChat && npm run backend:dev
cd viventium_v0_4/LibreChat && npm run frontend:dev
cd viventium_v0_4/LibreChat && npm run test:api
cd viventium_v0_4/LibreChat && npm run test:client
cd viventium_v0_4/LibreChat && npm run lint

# Telegram / voice
cd viventium_v0_4/telegram-viventium && pytest
cd viventium_v0_4/voice-gateway && python3 -m pytest tests -q

# Agent sync: dry-run first, then narrow push mode explicitly
node viventium_v0_4/LibreChat/scripts/viventium-sync-agents.js pull --env=<env>
node viventium_v0_4/LibreChat/scripts/viventium-sync-agents.js compare --env=<env>
node viventium_v0_4/LibreChat/scripts/viventium-sync-agents.js push --prompts-only --dry-run --env=<env>
```

## Repo Topology

- `viventium_v0_4/` is the active product stack.
- `viventium_v0_4/LibreChat/` is a separate git repo and upstream fork boundary.
- `scripts/viventium/` owns install, upgrade, preflight, doctor, compile, bootstrap, and restore.
- `docs/requirements_and_learnings/` is the feature source of truth.
- `qa/` is the acceptance and evidence source of truth.
- `v0.3` docs are still useful for parity/history, but `v0.4` is the active implementation target.

## Read Before Coding

For any non-trivial task, read:

1. `docs/requirements_and_learnings/01_Key_Principles.md`
2. the relevant feature doc in `docs/requirements_and_learnings/`
3. `docs/02_ARCHITECTURE_OVERVIEW.md` and `docs/03_SYSTEMS_MAP.md`
4. the relevant file in `viventium_v0_4/docs/`
5. the matching QA doc in `qa/`

For install/runtime/release work, also read:

- `docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md`
- `docs/requirements_and_learnings/40_Public_Private_Boundaries_and_License_Matrix.md`
- `docs/requirements_and_learnings/45_Runtime_Feature_QA_Map.md`

## Quick Doc Map

- Background agents: `docs/requirements_and_learnings/02_Background_Agents.md`,
  `qa/background_agents/README.md`
- Telegram: `docs/requirements_and_learnings/03_Telegram_Bridge.md`,
  `viventium_v0_4/telegram-codex/docs/`,
  `qa/telegram_end_to_end.md`
- Voice and remote calls: `docs/requirements_and_learnings/06_Voice_Calls.md`,
  `docs/requirements_and_learnings/47_Remote_Access_and_Tunneling.md`,
  `viventium_v0_4/docs/VOICE_CALLS.md`,
  `qa/voice_playground_and_remote_calls.md`
- Auth, MCP, productivity: `docs/requirements_and_learnings/07_MCPs.md`,
  `docs/requirements_and_learnings/35_OAuth_Subscription_Auth.md`,
  `qa/mcp_oauth_and_productivity_integrations.md`
- Installer and publish safety: `docs/05_ENVIRONMENT.md`,
  `docs/06_TROUBLESHOOTING.md`,
  `qa/launch_readiness.md`,
  `qa/privacy_publish_audit.md`

## Investigation Rules

Before changing code:

1. Search all relevant surfaces: `docs/`, `qa/`, `scripts/`, `tests/`, and the runtime directories.
2. Do not stop at the first match. Find all references and the actual owning layer.
3. Trace the flow from trigger to config to runtime output to user-visible behavior.
4. Classify the issue:
   - runtime-generated
   - prompt/model-generated
   - source-of-truth drift
   - stale local state
5. Prefer the shared fix path over a local or one-surface workaround.
6. Read at least three files in the causal chain before proposing a fix.
7. Investigate at least one plausible alternative explanation before locking onto a root cause.

## Non-Negotiables

- Do not guess. Ground conclusions in code, config, docs, or runtime evidence.
- Do not hardcode by agent name, prompt text, tool substring, uploaded asset URL, user identity, or
  owner-machine state unless a source-of-truth doc explicitly requires it.
- No magic strings in behavior gates. If a conditional depends on a literal agent/provider/tool
  label, it should almost always be config- or constant-driven instead.
- Do not edit generated runtime files and call that a product fix.
- Do not solve runtime bugs with prompt hacks when the bug is in code, config generation, auth
  routing, sanitization, or UI logic.
- Do not overfit to one laptop, one conversation, or one test prompt.
- Do not claim success after partial verification.
- If the fix mirrors the user's exact complaint as a one-off special case, widen the investigation.
- Do not weaken snapshots, fixtures, baselines, or expected outputs just to make checks pass.

## Things That Will Bite You

- `viventium_v0_4/LibreChat/` has separate git history. Parent repo commits do not deploy it.
- Agent sync default push can overwrite tool arrays and break MCP links. Dry-run first and use the
  narrowest safe mode.
- Before any user-level agent push, review A/B/C drift:
  - A = live user-level bundle
  - B = tracked source-of-truth bundle
  - C = current repo changes not yet reflected in live
- Do not treat the tracked scaffold as automatically authoritative over live user edits to
  instructions, conversation starters, tools, model/provider, or background cortex config.
- Do not add regex or keyword matching in runtime code to detect user intent, provider selection,
  email phrasing, or productivity scope. Activation prompts plus `activation.fallbacks` own that
  behavior; runtime heuristics are a critical review block.
- If a user reports a capability disappearing, also inspect adjacent scaffold/runtime config such as
  `viventium_v0_4/LibreChat/viventium/source_of_truth/<env>.librechat.yaml`; a global toggle like
  `interface.webSearch` can disable the feature even when the agent tool array still includes it.
- Non-dry-run pushes should fail closed when reviewed live-vs-source drift still exists. Only use a
  follow-up acknowledgement such as `--compare-reviewed` after you have already shown the user the
  A/B/C diff and they intend to proceed.
- Generated runtime files in `~/Library/Application Support/Viventium/` are outputs, not canonical
  authoring inputs.
- A historically healthy owner machine is not the source of truth. Fresh compile/start on the
  current branch is.
- Raw LAN/IP browser voice is not valid local-install acceptance for microphone/WebRTC flows.
- Public exports must stay free of private identity, local paths, secrets, private docs, and
  operator-only state.

## Working Principles

- Explore first, then plan, then implement, then verify.
- Use small surgical changes that preserve upstream mergeability.
- In the LibreChat fork, wrap upstream modifications with `VIVENTIUM START` / `VIVENTIUM END`.
- Prefer config metadata, IDs, ACLs, declared capabilities, and tracked templates over human-facing
  labels or one-off heuristics.
- Fix shared layers when multiple surfaces are affected.
- Update the source-of-truth doc when product behavior changes.

## Testing And QA

- Run the smallest relevant automated tests, but run them.
- Inspect generated outputs for installer/compiler/runtime changes.
- Verify the real user-visible surface when the change affects UX.
- Name the verification gate you are claiming before you say a task is done:
  - `local dev gate`
  - `landing gate`
  - `release gate`
- Completion means verified, not merely edited: run checks, inspect generated artifacts when
  relevant, and confirm at least one real affected surface for user-visible changes.
- Use the QA docs as the acceptance contract, especially:
  - `qa/launch_readiness.md`
  - `qa/result_artifact_standard.md`
  - `qa/web_app_core_surface.md`
  - `qa/voice_playground_and_remote_calls.md`
  - `qa/mcp_oauth_and_productivity_integrations.md`
  - `qa/telegram_end_to_end.md`
  - `qa/background_agents/README.md`

## Surface Reminders

- Background agents must remain non-blocking and should use config-driven activation, not brittle
  string heuristics.
- Do not forward incomplete or in-progress assistant output to an external surface unless that
  surface's contract defines a streaming delivery mode.
- Telegram should preserve LibreChat parity unless a requirements doc explicitly says otherwise.
- Voice must preserve the same agent/runtime truth while being honest about topology, browser
  permissions, and remote-call limits.
- Connected-account flows must remain honest: supported account routing first, explicit BYOK second.

## Claude Workflow

- Start long or ambiguous tasks with explicit exploration before editing.
- For multi-step work, make a brief plan and keep it updated.
- Clear context between unrelated tasks.
- Compact early and include a focus string when the session gets large.
- Escalate effort for architecture, debugging, and verification-heavy work; use lighter effort for
  small mechanical edits.
- In shared workspaces, do not stash, switch branches, or touch another agent's worktree or
  unowned changes.
- Keep this file lean. If new guidance is path-specific or deeply specialized, prefer separate
  `.claude/rules/` files instead of growing this file indefinitely.

## Recommended Companion Files

These are not required to review this draft, but they are the next logical improvements:

- `.claudeignore` to keep large/noisy trees out of default exploration
- `.claude/rules/` for path-specific deep context
- a Stop hook for self-verification before Claude declares completion

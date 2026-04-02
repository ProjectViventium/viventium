# Viventium Core Agent Guide

This file is the proposed cross-agent operating contract for Viventium Core. It is intentionally
stronger than the current `AGENTS.md` and is designed to align with:

- `docs/requirements_and_learnings/01_Key_Principles.md`
- the rest of `docs/requirements_and_learnings/`
- `docs/01_PROJECT_VISION.md`, `docs/02_ARCHITECTURE_OVERVIEW.md`, `docs/03_SYSTEMS_MAP.md`
- `viventium_v0_4/docs/`
- `qa/`
- the Master Opus / CLAUDE guidance in `docs/master_opus_guide/`

## Mission

- Ship truthful, reusable, source-of-truth fixes.
- Optimize for end-to-end product correctness, not for one machine, one prompt, or one lucky path.
- Finish tasks completely: investigate, implement, verify, and document the result.

## Read First

Before changing code for any non-trivial task, read in this order:

1. `docs/README.md`
2. `docs/requirements_and_learnings/01_Key_Principles.md`
3. the feature-specific file in `docs/requirements_and_learnings/`
4. `docs/02_ARCHITECTURE_OVERVIEW.md` and `docs/03_SYSTEMS_MAP.md`
5. the relevant runtime docs in `viventium_v0_4/docs/`
6. the relevant QA runbook in `qa/`

If the task touches release/install/runtime behavior, also read:

- `docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md`
- `docs/requirements_and_learnings/40_Public_Private_Boundaries_and_License_Matrix.md`
- `docs/requirements_and_learnings/45_Runtime_Feature_QA_Map.md`
- `docs/requirements_and_learnings/47_Remote_Access_and_Tunneling.md`

## Repository Map

- `viventium_v0_4/` is the active v0.4 product stack.
- `viventium_v0_4/LibreChat/` is a separate git repo and must be treated as an upstream fork with
  independent commit/push flow.
- `viventium_v0_4/telegram-viventium/` is the Telegram bridge for the main product surface.
- `viventium_v0_4/telegram-codex/` is a standalone Telegram Codex sidecar with its own security and
  release rules.
- `viventium_v0_4/voice-gateway/` and `agent-starter-react/` own browser/call/playground voice
  behavior.
- `scripts/viventium/` owns installer, preflight, doctor, compiler, bootstrap, and restore flows.
- `docs/requirements_and_learnings/` is the source of truth for feature intent, constraints, edge
  cases, and product learnings.
- `qa/` is the source of truth for acceptance criteria and evidence expectations.
- `v0.3` documents remain useful for parity and historical reasoning, but `v0.4` is the active
  implementation target unless the task explicitly says otherwise.

## Task-To-Doc Map

- Background agents: `docs/requirements_and_learnings/02_Background_Agents.md`,
  `docs/requirements_and_learnings/52_Background_Agent_QA_and_Persona.md`,
  `qa/background_agents/`
- Telegram product surface: `docs/requirements_and_learnings/03_Telegram_Bridge.md`,
  `docs/requirements_and_learnings/52_Telegram_Codex_Standalone_Service.md`,
  `viventium_v0_4/telegram-codex/docs/`,
  `qa/telegram_end_to_end.md`,
  `qa/telegram_codex_standalone.md`
- Voice, calls, and remote access: `docs/requirements_and_learnings/06_Voice_Calls.md`,
  `docs/requirements_and_learnings/34_Voice_Chat_LLM_Override.md`,
  `docs/requirements_and_learnings/47_Remote_Access_and_Tunneling.md`,
  `viventium_v0_4/docs/VOICE_CALLS.md`,
  `qa/voice_playground_and_remote_calls.md`
- MCP, OAuth, connected accounts, and productivity tooling:
  `docs/requirements_and_learnings/07_MCPs.md`,
  `docs/requirements_and_learnings/35_OAuth_Subscription_Auth.md`,
  `docs/requirements_and_learnings/53_Workers_Projects_Runtime_MCP.md`,
  `docs/requirements_and_learnings/55_IDE_Subscription_Reuse_Findings_2026-03-27.md`,
  `qa/mcp_oauth_and_productivity_integrations.md`,
  `qa/connected_accounts_and_auth_recovery.md`
- Installer, config compiler, release hardening, and publish safety:
  `docs/05_ENVIRONMENT.md`,
  `docs/06_TROUBLESHOOTING.md`,
  `docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md`,
  `docs/requirements_and_learnings/40_Public_Private_Boundaries_and_License_Matrix.md`,
  `docs/requirements_and_learnings/41_Pre_Open_Source_Publish_Checklist.md`,
  `docs/requirements_and_learnings/43_Clean_Mac_Installer_QA.md`,
  `docs/requirements_and_learnings/45_Runtime_Feature_QA_Map.md`,
  `docs/requirements_and_learnings/50_ProjectViventium_Public_Release_Pipeline.md`,
  `qa/release_surface_and_publish_gate.md`,
  `qa/privacy_publish_audit.md`,
  `qa/launch_readiness.md`
- Memory, recall, and continuity: `docs/requirements_and_learnings/20_Memory_System.md`,
  `docs/requirements_and_learnings/32_Conversation_Recall_RAG.md`,
  `docs/requirements_and_learnings/46_Scheduled_Self_Continuity_Temporal_Freshness_2026-03-16.md`
- Web search and sanitization: `docs/requirements_and_learnings/24_LibreChat_Message_Rendering_and_Tags.md`,
  `docs/requirements_and_learnings/36_Web_Search_Safety_and_Relevance.md`,
  `docs/requirements_and_learnings/10_Open_Source_Web_Search.md`
- Standalone worker/project runtimes: `docs/requirements_and_learnings/18_Power_Agents_Beta.md`,
  `docs/requirements_and_learnings/54_Glass_Hive_Standalone_Runtime.md`,
  `viventium_v0_4/MCPs/power-agents-beta/README.md`

## Default Workflow

1. Explore before acting. Search the whole relevant surface, not just the first matching file.
2. Trace the full flow: trigger, config, runtime transformation, storage, API response, and
   user-visible output.
3. Classify the problem before editing:
   - runtime-generated
   - prompt/model-generated
   - config/compiler/generated-output drift
   - stale local state versus real source-of-truth issue
4. Reuse existing architecture and extension points before adding new code.
5. Make the smallest change that fixes the shared path.
6. Run targeted verification and inspect the actual generated/runtime artifacts.
7. Update the relevant documentation when product behavior, requirements, or operational truth
   changed.

## Anti-Shallow Gates

- Disprove yourself before proposing a fix. Investigate at least one plausible alternative
  explanation and rule it out with evidence rather than stopping at the first story that fits.
- Prove the cause twice. Be able to explain the same root cause from two independent directions,
  such as trigger-to-output and output-back-to-trigger.
- Read at least three files in the causal chain before proposing a fix:
  - trigger source
  - transformation/middleware/config layer
  - user-visible output surface
- If the proposed patch looks like the user's exact complaint turned into an `if` statement,
  suppression, or literal special case, stop and widen the investigation. Fix the category, not the
  single instance.

## Non-Negotiable Principles

- Do not guess. Every important claim should be anchored in code, config, logs, docs, or runtime
  evidence.
- Do not hardcode behavior that should come from config, metadata, capabilities, ACLs, provider
  support, or source-of-truth templates.
- Do not special-case by agent name, model name, prompt wording, tool substring, user identity, or
  one-off operator machine state unless the requirements explicitly authorize that exact behavior.
- Do not fix shared-product issues by editing generated runtime files, Mongo records, App Support
  leftovers, or private machine state and then calling the product fixed.
- Do not overfit to one laptop. If a clean install, remote access path, or fresh user flow would
  still fail, the fix is incomplete.
- Do not patch around a runtime bug with prompt text if the issue originates in runtime logic,
  config generation, sanitization, auth routing, or UI state.
- Do not create duplicate docs for the same feature. Extend the existing source-of-truth document.
- Do not claim success after partial work, static reasoning alone, or one-surface verification.

## Hardcoding And Overfitting Rules

The following are usually illegal unless a requirements doc explicitly says otherwise:

- branching on human-facing agent names
- branching on uploaded avatar/icon URLs
- branching on literal prompt phrases when the system should use structured metadata
- shipping machine-specific paths, tokens, uploaded asset IDs, or owner-private URLs
- synthesizing runtime defaults that disagree with tracked source-of-truth templates
- silently rewriting configured provider/model selections into some other model
- making the installer depend on owner-private runtime leftovers to appear healthy

Preferred alternatives:

- agent IDs, metadata, declared capabilities, ACL role, model family, config schema fields,
  source-of-truth YAML, canonical compiler inputs, and explicit feature flags

## String And Conditional Safety

- No magic strings in behavior gates. Any string literal used in a conditional, route match,
  filter, or special-case branch must come from an existing config field or constant, or be
  extracted into one before the change is considered complete.
- Inline comparisons against agent names, provider labels, tool suffixes, uploaded asset URLs, or
  user-visible titles are illegal unless a source-of-truth requirements doc explicitly mandates
  that exact literal behavior.

## Product Rules That Matter Across Many Tasks

- Background agents are additive and non-blocking. They must not delay the main reply.
- Telegram, web, scheduled, TTS, and voice surfaces should preserve the same underlying product
  truth unless a doc explicitly defines a surface-specific difference.
- Never forward incomplete or in-progress assistant output to an external surface unless that
  surface's contract defines a streaming delivery mode.
- User-facing labels should stay product-friendly. Internal neuroscience naming should not leak into
  the UI unless intentionally documented.
- Connected-account behavior must remain honest: use supported account flows where available, fall
  back to explicit BYOK when not, and never pretend a provider is connected when it is not.
- Web search, sanitization, memory, scheduling, and MCP features must be solved at the runtime
  layer when they are runtime problems.
- Public exports must not leak owner-private identity, private machine state, private docs, or
  secrets.

## Source-Of-Truth Rules

- Canonical human-edited user config is `~/Library/Application Support/Viventium/config.yaml`.
- Generated runtime files are outputs, not authoring surfaces.
- Public examples at repo root are documentation/reference surfaces, not the canonical installer
  input.
- The tracked source-of-truth templates and bundles under
  `viventium_v0_4/LibreChat/viventium/source_of_truth/` define shipped local defaults.
- Clean-machine acceptance is judged against a fresh compile/start on the current branch, not
  against a historically healthy owner machine.

## Implementation Rules

- Prefer new files, overlays, adapters, and existing extension points over broad invasive upstream
  edits.
- In `viventium_v0_4/LibreChat/`, wrap upstream modifications with `VIVENTIUM START` /
  `VIVENTIUM END` markers plus a short rationale.
- Keep JS/TS changes aligned with upstream LibreChat conventions:
  - TypeScript for new backend logic in `packages/api`
  - minimal legacy `/api` changes
  - no `any`
  - flat control flow and early returns
  - localized user-facing strings
- Keep Python code explicit, typed where practical, and easy to trace.
- Prefer structural fixes over prompt inflation.
- If a problem spans multiple surfaces, fix the shared layer instead of hand-patching each surface
  independently unless the architecture truly requires that split.

## Investigation Requirements

When investigating any serious bug, question, or feature:

1. Search across `docs/`, `qa/`, `scripts/`, `tests/`, and the relevant runtime directories.
2. Find all references, not just the first match.
3. Identify the feature doc and the QA doc before coding.
4. Trace config inputs and generated outputs when the behavior depends on installer/runtime state.
5. Check whether a nested repo boundary changes the correct place to edit or commit.
6. Check whether the issue is actually stale local state rather than current tracked source.
7. Look for at least one past or parallel implementation that solves the same category of problem
   before inventing a new pattern.

## Testing And Verification

- Run the smallest relevant automated tests, but do run them.
- For installer/compiler/runtime changes, inspect generated files instead of guessing.
- For product-facing changes, verify the real user-visible surface when practical.
- For remote or voice features, localhost-only inspection is not sufficient when the feature depends
  on topology, browser permissions, or public origins.
- Do not edit snapshots, expected-failure lists, fixtures, golden files, baselines, or similar
  verification artifacts merely to silence a failing check. Only change them when the underlying
  behavior intentionally changed, the new expectation is documented, and the changed behavior was
  verified as correct.
- Use `qa/` as the acceptance standard, especially:
  - `qa/launch_readiness.md`
  - `qa/result_artifact_standard.md`
  - `qa/web_app_core_surface.md`
  - `qa/voice_playground_and_remote_calls.md`
  - `qa/mcp_oauth_and_productivity_integrations.md`
  - `qa/telegram_end_to_end.md`
  - `qa/background_agents/`
- Completion means verified, not merely edited:
  - relevant tests or checks ran
  - generated artifacts were inspected and, when relevant, regenerated and diffed
  - at least one real affected surface was verified when the task changed user-visible behavior
- Do not say “done” if verification is still theoretical.

## Verification Gates

- Local Dev Gate:
  - targeted tests or checks for the changed area
  - generated/runtime artifacts inspected when relevant
  - root cause and at least one alternative explanation documented in working notes or handoff
- Landing Gate:
  - Local Dev Gate completed
  - broader regression checks for the touched surface
  - affected docs updated
  - nested repo / branch / source-of-truth boundaries confirmed
- Release Gate:
  - Landing Gate completed
  - relevant QA runbooks executed for the release surface
  - clean-machine, remote-origin, or publish-boundary checks run where applicable
  - no unresolved truthfulness gaps between docs, generated config, and live behavior

## Build, Test, And Dev Commands

- Unified stack launcher: `viventium_v0_4/viventium-librechat-start.sh`
- Public CLI: `bin/viventium`
- Installer: `./install.sh`
- Release tests: `python3 -m pytest tests/release/ -q`
- Compiler tests: `python3 -m pytest tests/release/test_config_compiler.py -q`
- LibreChat backend dev: `cd viventium_v0_4/LibreChat && npm run backend:dev`
- LibreChat frontend dev: `cd viventium_v0_4/LibreChat && npm run frontend:dev`
- LibreChat tests: `cd viventium_v0_4/LibreChat && npm run test:api` and
  `cd viventium_v0_4/LibreChat && npm run test:client`
- LibreChat quality: `cd viventium_v0_4/LibreChat && npm run lint && npm run format`
- Telegram bot tests: `cd viventium_v0_4/telegram-viventium && pytest`
- Voice gateway tests: `cd viventium_v0_4/voice-gateway && python3 -m pytest tests -q`

## Git, Branching, And Release Safety

- `viventium_v0_4/LibreChat/`, private repos, enterprise repos, and some nested components have
  separate git histories. Commit and push them independently.
- Never assume a parent repo commit deploys nested repo changes.
- Do not push nested repos to `upstream`; use their configured `origin`.
- Treat `git-helper.sh push ... --include-public-components` as a workspace push helper, not a full
  machine backup.
- Keep scratch automation output, local artifacts, caches, and nested temporary workspaces out of
  commits and public exports.
- Do not use blanket staging when a surgical commit is required.

## Multi-Agent Safety

- Do not stash to get around another agent's in-progress work.
- Do not switch branches, rewrite history, or “clean up” the workspace on behalf of another agent.
- Do not edit, move, or revert files you do not own in the current task unless explicitly asked.
- Do not touch another agent's worktree, temporary branch, or scratch area.
- Scope commits to your own changes and call out any observed overlapping edits before proceeding.

## Agent Sync Safety

- Always dry-run first.
- For prompt/instruction changes, use `--prompts-only`.
- Do not use default push unless the tool arrays and other synced fields are intentionally aligned
  and verified.
- After sync changes, verify the target runtime actually reloaded the intended data.

## Documentation Rules

- Keep one feature per requirements doc.
- Update docs when product truth changes, not weeks later.
- Distinguish current contract, historical context, and future ideas.
- Put future ideas in `docs/research_and_future_plans/`, not in source-of-truth requirements docs.
- Keep public docs free of private identity, secrets, and personal machine details.

## Definition Of Done

A task is only truly done when all of the following are true:

- the real cause was identified
- the fix targets the shared source-of-truth path
- relevant tests or runtime checks were run
- at least one alternative explanation was investigated and ruled out for non-trivial bugs
- affected user-visible surfaces were verified or explicitly called out as not verified
- relevant docs were updated
- no new private/public boundary leak was introduced
- no illegal hardcoding or one-machine overfitting was added

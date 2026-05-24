# Viventium Core

This is the proposed Claude-specific working file for Viventium Core. It stays lean on purpose and
pushes deep detail into the existing product docs instead of bloating the always-loaded context.

## Commands

```bash
# Public entrypoints
./install.sh
bin/viventium
viventium_v0_4/viventium-librechat-start.sh

# Stable local prod / side-by-side dev runtime
bin/viventium dev-runtime status
bin/viventium dev-env create dev
bin/viventium dev-env status dev
bin/viventium dev-env run dev start
bin/viventium dev-runtime activate-current --validate --restart --allow-protected-folder

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
- `docs/requirements_and_learnings/50_Stable_Dev_Runtime.md`
- `docs/requirements_and_learnings/51_GlassHive_Workflows_Self_Healing_and_Feature_Requests.md`
- `docs/requirements_and_learnings/52_Voice_Component_Fork_Modification_Inventory.md` when voice
  component pins, fork replay, LiveKit/playground routing, or voice release QA are in scope
- `qa/continuity-ops/README.md` when the work touches snapshots, restore, upgrade continuity, or helper backup UX

## Quick Doc Map

- Background agents: `docs/requirements_and_learnings/02_Background_Agents.md`,
  `qa/background_agents/README.md`
- Telegram: `docs/requirements_and_learnings/03_Telegram_Bridge.md`,
  `viventium_v0_4/telegram-codex/docs/`,
  `qa/telegram-runtime/README.md`, `qa/telegram-runtime/cases.md`, and relevant `qa/telegram-*`
  folders
- Voice and remote calls: `docs/requirements_and_learnings/06_Voice_Calls.md`,
  `docs/requirements_and_learnings/47_Remote_Access_and_Tunneling.md`,
  `docs/requirements_and_learnings/52_Voice_Component_Fork_Modification_Inventory.md`,
  `viventium_v0_4/docs/VOICE_CALLS.md`,
  `qa/modern-playground-voice/README.md`, `qa/modern-playground-voice/cases.md`, and relevant
  `qa/voice-*` folders
- Auth, MCP, productivity: `docs/requirements_and_learnings/07_MCPs.md`,
  `docs/requirements_and_learnings/40_Public_Private_Boundaries_and_License_Matrix.md`,
  `qa/mcp-oauth/`
- GlassHive (workstation sandbox): `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md`,
  `viventium_v0_4/GlassHive/docs/`
- Stable dev runtime and local work workflows:
  `docs/requirements_and_learnings/50_Stable_Dev_Runtime.md`,
  `docs/requirements_and_learnings/51_GlassHive_Workflows_Self_Healing_and_Feature_Requests.md`,
  `qa/stable-dev-runtime/README.md`, `qa/self-healing/README.md`,
  `qa/feature-request/README.md`, `qa/bug-report/README.md`
- Installer and publish safety: `docs/05_ENVIRONMENT.md`,
  `docs/06_TROUBLESHOOTING.md`,
  `qa/release-readiness/README.md`, `qa/release-readiness/cases.md`,
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
   - shipped-artifact / installed-bundle drift
5. If the issue involves memory, recall, restore, or upgrades, decompose it into distinct surfaces:
   - chat history
   - saved memory
   - recall / RAG corpus
   - schedules / background tasks
   - auth / provider state
   - restore / backup state
6. Prefer the shared fix path over a local or one-surface workaround.
7. Read at least three files in the causal chain before proposing a fix.
8. Investigate at least one plausible alternative explanation before locking onto a root cause.

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
- Treat any credential, password, token, or secret that appears in chat as a transient secret. Use
  it only for the immediate local task and never echo it into docs, tests, commits, QA artifacts,
  Claude prompts, or sub-agent handoffs.

## Things That Will Bite You

- `viventium_v0_4/LibreChat/` has separate git history. Parent repo commits do not deploy it.
- A nested component source fix is not shipped until the delivery surface that carries it is also
  updated and verified:
  - `components.lock.json` or other parent pin
  - compiled `dist/` outputs when the runtime executes them
  - prebuilt binaries and their source hashes when the product ships them
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
- Installed helpers, compiled bundles, and other shipped artifacts can drift from source. For those
  surfaces, verify the installed/running artifact, not just the source tree.
- Private companion and enterprise repos only count as private boundaries when they are separate git
  repo roots/worktrees, not plain same-named folders.
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

- Treat full-view evidence as the completion gate, not a nice-to-have. For every non-trivial feature,
  bug, runtime, installer, or release claim, connect:
  `feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`.
- Full-view evidence means reading the real owning code, docs and nested docs, scripts/harnesses,
  generated or shipped artifacts, logs, DB/state/persistence when applicable, and using the feature
  like a user through the relevant browser/computer, Telegram, voice, installer, CLI, MCP, scheduler,
  or GlassHive surface.
- Start QA from the complete feature inventory and natural user use cases, not from one visible
  symptom. Use `docs/requirements_and_learnings/45_Runtime_Feature_QA_Map.md`,
  `qa/feature-user-use-case-checklist.md`, and the owning `qa/<feature>/cases.md` to enumerate happy
  path, first-run/empty state, missing auth/config, degraded dependency, retry/recovery,
  interruption/cancel/update, persistence/reload/restart, cross-surface parity, generated/shipped
  artifact verification, and public/private safety before claiming coverage.
- Treat those use cases as a checklist. Every applicable item must be run like a user on the real
  surface and marked `PASS`, `FAIL`, `BLOCKED`, or `PARTIAL` with evidence.
- If the real user path cannot be executed, say `BLOCKED` or `PARTIAL`, name the missing surface, and
  do not claim completion from mocks, unit tests, source inspection, logs, DB rows, or model review.
- Supporting evidence cannot replace required user-path evidence.
- QA reports must make the evidence trail explicit: what was actually run, what was not run, visible
  UX/result evidence, supporting backend/log/DB evidence, and any mismatch or residual fix.
- Logs, DB rows, API responses, source inspection, model completions, and unit tests are supporting
  evidence, not substitutes for any required visible-UI, detail-state, persistence, or wording step.
- For voice, LiveKit, Telegram voice, browser-audio, or TTS/STT changes, follow `qa/README.md`:
  first prove the changed code/config is present in the active runtime artifact being tested: source
  checkout, generated config, built artifact, and installed/running process as applicable. Then run
  the actual playground/call/bot path with synthetic public-safe content. Verify the audible or
  delivered voice outcome, synthetic or sanitized transcript evidence, interruption/cancel behavior
  when relevant, latency/log visibility, DB/state persistence, runtime config alignment, and owning
  code. Instrumentation-only confidence, source inspection, logs, DB rows, unit tests, model review,
  Claude review, or "the next call should show it" is `PARTIAL`, not acceptance.
- For evidence-retrieval failures, classify the failure before answering. Successful empty results,
  provider unavailable, timeout, rate limit, auth/config missing, request rejected, unsupported
  configuration, and missing local prerequisites such as Docker-backed search services are different
  outcomes. For named-entity/contact/date/current-fact lookups, one failed web search should trigger
  provider-health inspection plus browser/computer/local-delegation fallback when available.
- For GlassHive/local-delegation dispatch, preserve the user's target and success condition, inspect
  any returned instruction audit, write the acknowledgement in your own voice, and do not quote a
  canned status template or expose worker/run/project plumbing unless diagnostics were requested.
- Follow `qa/README.md` as the QA operating contract. For user-visible changes, use the full-view
  evidence loop there: exercise the feature like a user, inspect visible and expanded/detail states,
  check refresh or persistence when relevant, compare with code/log/DB/generated-artifact evidence,
  and verify final user-facing wording before claiming done.
- Run the smallest relevant automated tests, but run them.
- Inspect generated outputs for installer/compiler/runtime changes.
- Verify the real user-visible surface when the change affects UX.
- For components with prebuilt binaries, compiled `dist/` bundles, or shipped helper apps, prove the
  live installed/shipped artifact independently. Source correctness does not imply artifact
  correctness.
- Name the verification gate you are claiming before you say a task is done:
  - `local dev gate`
  - `landing gate`
  - `release gate`
- Completion means verified, not merely edited: run checks, inspect generated artifacts when
  relevant, and confirm at least one real affected surface for user-visible changes.
- If a nested repo or shipped artifact changed, verification is incomplete until the parent pin, the
  built artifact, and the installed artifact all match the intended fix.
- Use the QA docs as the acceptance contract, especially:
  - `qa/README.md`
  - `qa/_templates/run-report.md`
  - `qa/release-readiness/README.md`
  - `qa/release-readiness/cases.md`
  - `qa/background_agents/README.md`
  - `qa/telegram-runtime/README.md`
  - `qa/modern-playground-voice/README.md`

## Surface Reminders

- Background agents must remain non-blocking and should use config-driven activation, not brittle
  string heuristics.
- Do not forward incomplete or in-progress assistant output to an external surface unless that
  surface's contract defines a streaming delivery mode.
- Telegram should preserve LibreChat parity unless a requirements doc explicitly says otherwise.
- Voice must preserve the same agent/runtime truth while being honest about topology, browser
  permissions, and remote-call limits.
- Connected-account flows must remain honest: supported account routing first, explicit BYOK second.
- Stable dev runtime work must preserve the local-prod/dev-env boundary: installed helper/runtime is
  local prod, `bin/viventium dev-env` is optional side-by-side development, heavy singleton services
  remain shared by default, and promotion uses `bin/viventium dev-runtime activate-current --validate
  --restart` instead of copying source into install paths.

## Claude Workflow

- Start long or ambiguous tasks with explicit exploration before editing.
- For multi-step work, make a brief plan and keep it updated.
- Clear context between unrelated tasks.
- Compact early and include a focus string when the session gets large.
- Escalate effort for architecture, debugging, and verification-heavy work; use lighter effort for
  small mechanical edits.
- Before handing context to Claude or another sub-agent, sanitize private values when a redacted
  placeholder is sufficient. Do not forward live secrets just because they appeared in chat.
- In shared workspaces, do not stash, switch branches, or touch another agent's worktree or
  unowned changes.
- Keep this file lean. If new guidance is path-specific or deeply specialized, prefer separate
  `.claude/rules/` files instead of growing this file indefinitely.

## Recommended Companion Files

These are not required to review this draft, but they are the next logical improvements:

- `.claudeignore` to keep large/noisy trees out of default exploration
- `.claude/rules/` for path-specific deep context
- a Stop hook for self-verification before Claude declares completion

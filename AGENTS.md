# Viventium Core

Lean repository-specific instructions for Codex. Keep this file short, concrete, and focused on
Viventium-specific rules; deep feature truth belongs in the existing docs.

## Read Before Coding

For any non-trivial task, read:

1. `docs/requirements_and_learnings/01_Key_Principles.md`
2. the relevant feature doc in `docs/requirements_and_learnings/`
3. `docs/02_ARCHITECTURE_OVERVIEW.md` and `docs/03_SYSTEMS_MAP.md`
4. the relevant runtime doc in `viventium_v0_4/docs/`

For installer, runtime, release, or publish-boundary work, also read:

- `docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md`
- `docs/requirements_and_learnings/40_Public_Private_Boundaries_and_License_Matrix.md`
- `docs/requirements_and_learnings/45_Runtime_Feature_QA_Map.md`
- `docs/requirements_and_learnings/47_Remote_Access_and_Tunneling.md`
- `docs/requirements_and_learnings/50_Stable_Dev_Runtime.md`
- `docs/requirements_and_learnings/51_GlassHive_Workflows_Self_Healing_and_Feature_Requests.md`
- `docs/requirements_and_learnings/52_Voice_Component_Fork_Modification_Inventory.md` when the
  work touches voice component pins, fork replay, LiveKit/playground routing, or voice release QA
- `qa/continuity-ops/README.md` when the work touches snapshots, restore, upgrade continuity, or helper backup UX
- the relevant files under `qa/`, if they already exist for the feature or release surface

## Repo Topology

- `viventium_v0_4/` is the active product stack.
- `viventium_v0_4/LibreChat/` is a separate git repo and upstream fork boundary.
- `scripts/viventium/` owns install, configure, upgrade, preflight, doctor, compile, bootstrap,
  and restore.
- `docs/requirements_and_learnings/` is the feature source of truth; extend existing docs instead
  of creating duplicates for the same feature.
- `qa/` is the acceptance and evidence source of truth.
- Managed component repos live under `viventium_v0_4/...` and are pinned by `components.lock.json`;

## Public / Private Boundary

- This repo is only for public-safe product code, tests, docs, examples, and release tooling.
- Keep secrets, personal data, customer data, private prompts, private docs, exports, screenshots,
  attachments, snapshots, logs, App Support state, generated runtime env files, and machine-local
  artifacts out of this repo.
- Public docs, QA reports, fixtures, examples, and commit history must not expose local usernames,
  hostnames, personal emails, home-directory paths, laptop names, or secret-bearing command lines.
  Use public-safe placeholders such as `/path/to/viventium`, `~/Library/Application Support/...`,
  `<temp>`, `example.com`, and synthetic non-personal values.
- Do not reuse QA accounts, brand names, business domains, customer names, or private operating
  context from another project. Viventium repo, runtime QA, and public evidence must stay
  Viventium-scoped unless a source-of-truth doc explicitly requires an integration boundary.
- Treat credentials, passwords, tokens, and secrets that appear in chat as transient secrets. They
  must not be echoed into docs, tests, commits, QA artifacts, Claude prompts, or sub-agent handoffs.
- If something is useful but not public-safe, move it to the designated
  `<viventium-private-user>` or `<enterprise-deployment-repo>` outside this tree. If those repos
  are nested locally for workspace convenience, they must remain separate git repos, ignored by the
  main repo, and excluded from public exports.
- A plain folder named like a private companion or enterprise repo is not a valid boundary. It only
  counts when it is the root of a separate git repo or worktree.
- Canonical local config and runtime state live outside git:
  - `~/Library/Application Support/Viventium/config.yaml`
  - `~/Library/Application Support/Viventium/runtime/*`
  - `~/Library/Application Support/Viventium/state/*`
  - macOS Keychain
- Generated runtime files are outputs, not authoring surfaces.
- Secret-bearing QA presets or transfer files may exist only as temporary local files or in the
  designated private repo, never as tracked public artifacts.

## Working Rules

- Take full ownership end to end. For any non-trivial feature, bug, or release task: study the
  foundation, trace the real owning layers, compare alternatives, design the fix, implement it,
  test it, QA it, and document the resulting product truth.
- Trace the real owning path before editing: trigger -> config/compiler -> runtime -> user-visible
  output.
- For local stable-runtime work, keep the modes distinct:
  - local prod is the installed user-facing runtime started by the helper
  - dev envs are optional side-by-side runtimes with separate app-facing ports/state
  - heavy singleton services stay shared by default: recall/RAG, SearXNG, Firecrawl, Google Workspace MCP, and Microsoft 365 MCP
  - promoting a local checkout uses `bin/viventium dev-runtime activate-current --validate --restart`; do not copy source into install paths
- For install/runtime/release fixes, classify the delivery surfaces separately:
  - tracked source
  - parent component pin / manifest
  - compiled or prebuilt shipped artifact
  - live installed or running artifact
- For memory, recall, restore, or upgrade incidents, decompose the problem across:
  - chat history
  - saved memory
  - recall / RAG corpus
  - schedules / background tasks
  - auth / provider state
  - restore / backup state
- Prefer shared structural fixes over one-off patches, hacks, or owner-machine workarounds.
- Do not hardcode on agent names, prompt text, tool substrings, provider labels, user identity, or one machine's state unless a source-of-truth doc explicitly requires it.
- CRITICAL RULE: do not add regex or keyword matching in runtime code to detect user intent, provider selection, email phrasing, or productivity scope. Activation prompts in `viventium_v0_4/LibreChat/viventium/source_of_truth/<env>.viventium-agents.yaml` own that behavior; classifier outages are solved with `activation.fallbacks`, not heuristics.
- If a proposed fix looks like the user's exact complaint turned into an `if` statement, widen the
  investigation first.
- In the LibreChat fork, wrap upstream modifications with `VIVENTIUM START` / `VIVENTIUM END` plus
  a short rationale.
- Do not edit generated App Support files, Mongo data, or local runtime leftovers and call that a
  product fix.
- Update the owning requirements doc when product truth changes.

## Legal / Illegal Fix Patterns

- Usually illegal unless a source-of-truth doc explicitly requires it:
  - branching on human-facing agent names
  - branching on prompt text, tool substrings, or uploaded asset URLs
  - branching on provider labels or user-visible titles when structured metadata exists
  - shipping machine-specific paths, private URLs, tokens, or owner-private artifacts
  - silently remapping configured models/providers to something else
  - making the installer appear healthy by relying on one laptop's leftovers
  - using real personal or confidential data in tests, fixtures, or screenshots
- Preferred alternatives:
  - config schema fields
  - source-of-truth YAML/templates
  - IDs, metadata, ACLs, declared capabilities, and feature flags
  - synthetic non-personal test data

## Second Opinion Workflow

- For non-trivial architecture, debugging, forensic, or release work, finalize your own proposal
  first. Do not use another model to think in your place.
- After you have a grounded proposal, get a review-only second opinion from a local Claude CLI
  helper when available.
- Default Claude to review-only. Explicitly tell it not to make changes and to present findings and
  recommendations for review and approval.
- Give Claude the full picture: the relevant docs, exact files, runtime evidence, your provisional
  root cause, at least one alternative explanation already considered, and the exact decision you
  want validated or challenged.
- Sanitize secrets, credentials, and private values before handing context to Claude or any sub-agent
  unless the exact value is strictly required for a local machine-only step.
- When useful, run the original user task or project prompt through the same review-only Claude
  pass to compare its reasoning against your own.
- Treat Claude as a second opinion, not the source of truth.

## Git And Repo Safety

- Nested repos have separate histories. Parent repo commits do not deploy nested repo changes.
- Before claiming a fix is shipped or release-ready, verify that the nested component commit, the
  parent pin or manifest entry (for example `components.lock.json`), and any compiled/prebuilt
  delivery artifact all reflect the intended change.
- Commit and push nested repos independently to their configured `origin`, never `upstream`.
- Treat `git-helper.sh push ... --include-public-components` as a workspace helper, not a backup.
- Keep scratch output, caches, local artifacts, temporary workspaces, and generated service state
  out of commits and public exports.
- Do not blanket-stage when a surgical commit is required.
- Before any public commit, push, or PR from this repo, verify author and committer identity are set
  to an approved public-safe name/email. Never rely on shell or hostname-derived git defaults.
- Before any public push or PR, scan staged diffs and QA/report files for local absolute paths,
  personal identifiers, machine names, and private command examples.
- If a leaked identity or private path has already entered branch history intended for public review,
  create a fresh review branch from a clean base, recommit with sanitized metadata, push that clean
  branch, and delete the leaked review branch instead of asking reviewers to use the dirty history.

## Agent Sync Safety

- Before any user-level agent push, run `viventium-sync-agents.js compare --env=<env>` (or an
  equivalent live-vs-source review) and inspect:
  - A: current live user-level agent config
  - B: tracked source-of-truth bundle
  - C: current repo/source-of-truth edits still not in live
- Present the A/B/C drift to the user before applying a sync when live user-managed fields differ.
- If the reported symptom is capability availability, also inspect adjacent scaffold/runtime config
  such as `viventium_v0_4/LibreChat/viventium/source_of_truth/<env>.librechat.yaml`; global
  toggles like `interface.webSearch` can disable behavior even when the agent bundle still carries
  the expected tool.
- Non-dry-run pushes should fail closed when reviewed live-vs-source drift still exists; only use a
  follow-up acknowledgement such as `--compare-reviewed` after you have already presented the drift
  and intentionally accepted it.
- Always dry-run first.
- For prompt/instruction changes, use `--prompts-only`.
- Treat live user edits to instructions, conversation starters, tools, model/provider, and
  background cortex config as protected state until they are intentionally reconciled.
- Do not use default push unless the synced fields were intentionally reviewed.
- After sync changes, verify the target runtime actually reloaded the intended data.

## Verification

- Full-view evidence is the default completion gate for non-trivial work. Before claiming a feature,
  bug fix, runtime change, installer change, or release task is done, connect:
  `feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`.
- Full-view evidence means inspecting the real owning code, docs and nested docs, scripts/harnesses,
  generated or shipped artifacts, logs, DB/state/persistence when applicable, and the real user path
  through browser/computer, Telegram, voice, installer, CLI, MCP, scheduler, or GlassHive surfaces.
- Start QA from the complete feature inventory and natural user use cases. Use
  `docs/requirements_and_learnings/45_Runtime_Feature_QA_Map.md`,
  `qa/feature-user-use-case-checklist.md`, and the owning `qa/<feature>/cases.md` to enumerate the
  obvious user actions first: happy path, first-run/empty state, missing auth/config, degraded
  dependency, retry/recovery, interruption/cancel/update, persistence/reload/restart, cross-surface
  parity, generated/shipped artifact verification, and public/private safety.
- Treat the enumerated use cases as a checklist. Every applicable item must be run like a user on the
  real surface and marked `PASS`, `FAIL`, `BLOCKED`, or `PARTIAL` with supporting evidence before a
  completion or release-readiness claim.
- If a real user path is required and cannot be run in the current environment, mark the result
  `BLOCKED` or `PARTIAL`, explain the exact missing surface, and do not substitute mocks, unit tests,
  source inspection, logs, DB rows, or another model's review for that missing user evidence.
- Supporting evidence cannot replace required user-path evidence.
- Every user-visible QA report must state what was actually run, what was not run, what evidence
  proves the visible UX/result, and what fix remains for any mismatch.
- Run the smallest relevant automated checks, but run them.
- Do not stop at the tiniest local test when the change can affect broader flows. Professionally
  test all realistically affected paths around what you changed.
- For installer, compiler, or runtime changes, inspect generated outputs and verify at least one
  real affected surface.
- For helpers, bundled apps, compiled `dist/` outputs, or other prebuilt artifacts, verify the live
  installed/shipped artifact independently. Source correctness is not enough.
- Clean-machine acceptance beats "works on the owner laptop."
- Use `qa/` as the home for end-to-end QA plans and reports. If the needed feature area does not
  exist yet, create it instead of scattering QA notes elsewhere.
- Follow `qa/README.md` as the QA operating contract. Keep one living QA source of truth per feature
  or flow, update its cases before or alongside the code change, and save dated public-safe results
  under the owning feature folder.
- Every escaped bug or production miss must become a reusable synthetic regression case in the
  relevant `qa/<feature>/cases.md`, with expected outcome, forbidden result, evidence to capture,
  and last-run status.
- For evidence-retrieval failures, do not hand-wave. Distinguish successful empty results from
  provider unavailable, timeout, rate limit, auth/config missing, request rejected, unsupported
  configuration, and missing local prerequisites such as Docker-backed search services. For
  named-entity/contact/date/current-fact lookups, a failed web search triggers provider-health
  inspection plus browser/computer/local-delegation fallback when available.
- For GlassHive/local-delegation dispatch, do not quote canned acknowledgement text. Preserve the
  user's target and success condition in the delegated instruction, inspect the returned audit when
  present, then write a short acknowledgement in your own voice and let callbacks carry the result.
- For non-trivial feature or bug work, run an independent QA pass after implementation. Prefer a
  separate agent or clearly separated QA pass, and save public-safe evidence and findings under
  `qa/<feature>/`.
- Use real-browser QA for browser-facing flows, such as Playwright CLI or equivalent. The minimum
  acceptance loop is: real browser prompt/action -> visible UI outcome -> expanded/detail state ->
  refresh or persistence check when relevant -> backend/log/DB confirmation -> final wording does
  not contradict the visible state.
- For voice, LiveKit, Telegram voice, browser-audio, or TTS/STT changes, the completion gate is a
  real user-grade surface run after the changed code/config is proven present in the active runtime
  artifact being tested: source checkout, generated config, built artifact, and installed/running
  process as applicable. Run the actual playground/call/bot path with synthetic public-safe content,
  capture timestamped evidence of what was heard or delivered, and correlate it with logs, DB/state,
  generated config, and owning code.
  Do not claim the fix is done with wording like "the next call should show..." or "instrumentation
  is ready"; that is `PARTIAL` until a post-change user-path run proves the behavior.
  Use `qa/modern-playground-voice/cases.md` `MPV-014` as the reusable acceptance case for affected
  voice fixes.
- Browser-facing work must be tested through Playwright CLI or an equivalent real browser. Voice and
  audio-facing browser work must also verify the audible or delivered voice outcome, synthetic or
  sanitized transcript evidence, interruption/cancel behavior when relevant, latency/log visibility,
  DB/state persistence, and runtime config alignment. If the audible or delivered voice path cannot
  be run, mark the result `BLOCKED` or `PARTIAL` and name the exact missing prerequisite.
- For non-trivial forensic or architecture work, obtain the Claude review-only second opinion when
  available after your own evidence-backed RCA/proposal and before final acceptance. Claude review is
  supporting evidence; it does not replace the real browser/voice/user path, logs, DB/state, code
  trace, or tests.
- Logs, DB rows, API responses, source inspection, model completions, and unit tests are supporting
  evidence, not substitutes for any required visible-UI, detail-state, persistence, or wording step.
- Do not rely on mocked-only tests to justify end-to-end claims. Use synthetic non-personal test
  data, and never expose secrets, private chats, attachments, or customer data in QA artifacts.
- When release or public-readiness is in scope, use `qa/` as the acceptance contract.
- For installer/public-release QA, prove the product through supported public entrypoints and keep
  public-safe QA writeups phrased in those terms. If an internal harness is needed for debugging,
  keep it sanitized and clearly separate it from the public install story.
- Before stopping on public-facing work, ask:
  1. Is this safe to go public now?
  2. Has fresh clone/install been proven in a new directory?
  3. Did I verify that no private identity, secret, or local-path leakage is being published with this work?
  4. If a nested component or shipped artifact changed, did I verify the parent pin, built artifact, and installed artifact all match?
- Do not say "done" if verification is still theoretical.

## Useful Commands

- Installer: `./install.sh`
- Public CLI: `bin/viventium`
- Full stack launcher: `viventium_v0_4/viventium-librechat-start.sh`
- Inspect installed local prod checkout: `bin/viventium dev-runtime status`
- Create side-by-side dev runtime: `bin/viventium dev-env create dev`
- Run/check side-by-side dev runtime: `bin/viventium dev-env run dev start` and `bin/viventium dev-env run dev status`
- Promote current checkout to installed local prod: `bin/viventium dev-runtime activate-current --validate --restart --allow-protected-folder`
- Public refresh flow: `bin/viventium upgrade --restart`
- Release tests: `python3 -m pytest tests/release/ -q`
- Compiler tests: `python3 -m pytest tests/release/test_config_compiler.py -q`
- LibreChat backend dev: `cd viventium_v0_4/LibreChat && npm run backend:dev`
- LibreChat frontend dev: `cd viventium_v0_4/LibreChat && npm run frontend:dev`
- LibreChat tests: `cd viventium_v0_4/LibreChat && npm run test:api && npm run test:client`
- Telegram tests: `cd viventium_v0_4/telegram-viventium && pytest`
- Voice gateway tests: `cd viventium_v0_4/voice-gateway && python3 -m pytest tests -q`

## Keep This File Lean

- Put deep feature detail in `docs/requirements_and_learnings/`.
- Put path-specific or tool-specific depth in the owning subtree docs.
- Keep `AGENTS.md` focused on repo topology, boundaries, commands, and non-obvious project rules.

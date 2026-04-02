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
- If something is useful but not public-safe, move it to the designated
  `<viventium-private-user>` or `<enterprise-deployment-repo>` outside this tree. If those repos
  are nested locally for workspace convenience, they must remain separate git repos, ignored by the
  main repo, and excluded from public exports.
- Canonical local config and runtime state live outside git:
  - `~/Library/Application Support/Viventium/config.yaml`
  - `~/Library/Application Support/Viventium/runtime/*`
  - `~/Library/Application Support/Viventium/state/*`
  - macOS Keychain
- Generated runtime files are outputs, not authoring surfaces.

## Working Rules

- Take full ownership end to end. For any non-trivial feature, bug, or release task: study the
  foundation, trace the real owning layers, compare alternatives, design the fix, implement it,
  test it, QA it, and document the resulting product truth.
- Trace the real owning path before editing: trigger -> config/compiler -> runtime -> user-visible
  output.
- Prefer shared structural fixes over one-off patches, hacks, or owner-machine workarounds.
- Do not hardcode on agent names, prompt text, tool substrings, provider labels, user identity, or one machine's state unless a source-of-truth doc explicitly requires it.
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
- When useful, run the original user task or project prompt through the same review-only Claude
  pass to compare its reasoning against your own.
- Treat Claude as a second opinion, not the source of truth.

## Git And Repo Safety

- Nested repos have separate histories. Parent repo commits do not deploy nested repo changes.
- Commit and push nested repos independently to their configured `origin`, never `upstream`.
- Treat `git-helper.sh push ... --include-public-components` as a workspace helper, not a backup.
- Keep scratch output, caches, local artifacts, temporary workspaces, and generated service state
  out of commits and public exports.
- Do not blanket-stage when a surgical commit is required.

## Agent Sync Safety

- Always dry-run first.
- For prompt/instruction changes, use `--prompts-only`.
- Do not use default push unless the synced fields were intentionally reviewed.
- After sync changes, verify the target runtime actually reloaded the intended data.

## Verification

- Run the smallest relevant automated checks, but run them.
- Do not stop at the tiniest local test when the change can affect broader flows. Professionally
  test all realistically affected paths around what you changed.
- For installer, compiler, or runtime changes, inspect generated outputs and verify at least one
  real affected surface.
- Clean-machine acceptance beats "works on the owner laptop."
- Use `qa/` as the home for end-to-end QA plans and reports. If the needed feature area does not
  exist yet, create it instead of scattering QA notes elsewhere.
- Keep one living QA source of truth per feature or flow. Start by writing the QA plan and test
  cases, then execute against that plan.
- For non-trivial feature or bug work, run an independent QA pass after implementation. Prefer a
  separate agent or clearly separated QA pass, and save public-safe evidence and findings under
  `qa/<feature>/`.
- Use real-browser QA for user-facing flows when relevant, such as Playwright CLI or equivalent
  browser automation.
- Do not rely on mocked-only tests to justify end-to-end claims. Use synthetic non-personal test
  data, and never expose secrets, private chats, attachments, or customer data in QA artifacts.
- When release or public-readiness is in scope, use `qa/` as the acceptance contract.
- Before stopping on public-facing work, ask:
  1. Is this safe to go public now?
  2. Has fresh clone/install been proven in a new directory?
- Do not say "done" if verification is still theoretical.

## Useful Commands

- Installer: `./install.sh`
- Public CLI: `bin/viventium`
- Full stack launcher: `viventium_v0_4/viventium-librechat-start.sh`
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

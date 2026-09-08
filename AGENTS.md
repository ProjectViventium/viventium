# Viventium Core

Repository-specific instructions shared by Codex and Claude. Product truth belongs in the owning
docs and tests; repeatable workflows belong in skills; deterministic enforcement belongs in code,
tests, permissions, or hooks.

## Instruction Architecture And Model Contract

- This file is the canonical shared project instruction layer. Root `CLAUDE.md` imports it. State
  shared project rules once; do not copy them into model-specific files.
- Codex discovery stops at the active git root. A session started inside a nested component repo
  does not auto-load this parent file, so Viventium-managed nested `AGENTS.md` files explicitly
  require this parent contract where it applies.
- Claude Code loads parent `CLAUDE.md` files and discovers nested files on demand. Root `CLAUDE.md`
  imports this file; a nested `CLAUDE.md` imports only its colocated `AGENTS.md`.
- Give agents the complete outcome, relevant context, constraints, required evidence, success
  criteria, and output shape once. Do not prescribe reasoning they can infer or add generic
  “think harder,” repeated re-check, or mandatory verifier prompts.
- Use plans, skills, and subagents only when they materially help. Delegate only genuinely
  independent, sizeable work; keep small tasks local.
- Deliver what the user asked for at the intended scope. Make routine in-scope judgments yourself.
  Ask only when different interpretations would cause materially different work.
- <a id="communication"></a> **CORE-015:** Report the result briefly, plainly, and truthfully,
  including any open evidence gate.

## Action Boundaries

- For answer, explain, review, diagnose, or plan requests: inspect relevant materials and report the
  result. Do not implement changes unless requested.
- For change, build, or fix requests: make the requested in-scope local changes and run relevant
  non-destructive validation without asking first.
- Require confirmation for external writes, destructive actions, purchases, public release, or a
  material expansion of scope.
- Preserve unrelated user or agent changes. Do not stash, switch branches, blanket-stage, commit,
  push, or open a PR unless the user asks for that action. **CORE-014**
- **GOV-013:** Persist through routine authorized local blockers, but never expand authority or
  bypass a real approval or security boundary.

## Core Outcome Metric

**outcome = Quality (Intelligence, Relevance, Usefulness, Alignment) + Performance (Fast, Smooth, Reliable)**
are the core metric of the viventium project that we must always evaluate in tests, QA, development, design.
Never optimize Performance in isolation — a faster result that is less intelligent, relevant, useful, or
aligned is a regression. Where multiple paths can serve the same request (e.g. an in-process hand-off agent
vs a GlassHive worker), aim for **parity**: each path must meet this metric on its own AI. Do not hardcode a
routing rubric ("which path for which request"); let the Main Agent and worker decide intelligently, and make
every path truthful, complete, useful, and fast.

## Read By Relevance

For non-trivial product work, read only the sources needed for the owning path:

1. `docs/requirements_and_learnings/01_Key_Principles.md`
2. the owning capability or retained feature doc linked from `docs/README.md`
3. `docs/architecture/overview.md` and `docs/architecture/systems-map.md` when cross-system context matters
4. the relevant runtime doc under `viventium_v0_4/docs/`
5. the owning journey in `qa/catalog.yaml` and its linked detailed case banks

For installer, runtime, release, publish-boundary, continuity, or voice-component work, follow the
active owner and QA journey linked from `docs/README.md`. The migration-era
`docs/requirements_and_learnings/45_Runtime_Feature_QA_Map.md` remains a compatibility map, not the
current status owner. Do not load the whole documentation tree for a narrow change.

## Repository And Delivery Boundaries

- `viventium_v0_4/` is the active product stack.
- `scripts/viventium/` owns install, configure, upgrade, preflight, doctor, compile, bootstrap, and
  restore.
- `docs/requirements_and_learnings/` is the feature source of truth. Extend the owning document
  instead of creating a duplicate.
- `qa/` is the acceptance and evidence source of truth; follow `qa/README.md`.
- Managed components under `viventium_v0_4/` may be separate git repos. Confirm the active root with
  `git rev-parse --show-toplevel` before editing or reporting status.
- `viventium_v0_4/LibreChat/` is the upstream-fork boundary. Its local instructions own fork markers
  and agent-sync safeguards.
- `viventium_v0_4/GlassHive/` is a separate component. Its local instructions own worker/runtime
  rules; the cross-boundary brokerage invariant is shared below.
- A nested source change is not shipped until the component commit, parent pin in
  `components.lock.json`, compiled/prebuilt artifact, and installed/running artifact agree where
  applicable.
- If the user authorizes a nested-repo push, push each component to its configured `origin`, never
  `upstream`.

<a id="private-evidence"></a>

## Public And Private Safety

- **CC-064 / GOV-004:** Keep recoverable byte-exact source and thread evidence, stable IDs, hashes,
  and superseded history private. Publish only sanitized requirements, decisions, QA, evidence, and
  gaps.
- This repo contains only public-safe product code, tests, docs, examples, and release tooling.
- Never track secrets, credentials, personal/customer data, private prompts/docs, exports,
  screenshots, attachments, snapshots, logs, generated runtime env files, or machine-local state.
- Public artifacts and history must not expose usernames, hostnames, personal emails, device names,
  private URLs, absolute home paths, or secret-bearing commands. Use synthetic values and public-safe
  placeholders.
- Do not reuse real QA accounts, brands, business domains, customer names, or private operating
  context from another project.
- Treat secrets in chat as transient. Do not echo them into files, QA evidence, commits, reviewer
  prompts, or subagent handoffs.
- Private companion and enterprise folders count as boundaries only when they are separate git repos
  or worktrees and are excluded from public exports.
- Canonical local config and runtime state live under `~/Library/Application Support/Viventium/`
  and macOS Keychain. Generated runtime files are outputs, not authoring surfaces.
- If private identity or paths enter history intended for public review, rebuild the review branch
  from a clean base with sanitized metadata and abandon the contaminated branch.

<a id="change-discipline"></a>

## Implementation Invariants

- **CORE-005 / GOV-010:** Prefer the smallest proven native mechanism and reuse existing Viventium,
  LibreChat, GlassHive, Codex, and Claude primitives.
- **GOV-007:** Revalidate primary sources and current candidate identity before correcting a
  contradiction, stale state, broken owner, or invalid evidence.
- Trace the owning flow before editing: trigger -> config/compiler -> runtime -> user-visible output.
- Prefer shared structural fixes over complaint-specific branches or owner-machine workarounds.
- Viventium is AI-first: rely on model intelligence for semantic judgment. Give the model the goal,
  relevant context, structured capabilities, and evidence; do not hardcode or overfit runtime
  behavior to one prompt, phrase, agent, provider, tool, user, complaint, conversation, machine, or
  use case. If a proposed fix looks like the user's exact complaint turned into an `if` statement,
  widen the investigation first.
- Do not branch on human-facing agent names, prompt text, tool substrings, uploaded URLs, provider
  labels, user identity, or one machine's state when structured metadata can own the decision.
- CRITICAL: do not add regex or keyword matching in runtime code to detect user intent, provider
  selection, email phrasing, or productivity scope. Source-of-truth prompts and
  `activation.fallbacks` own model judgment; runtime owns typed structure.
- Prefer config schema fields, IDs, metadata, ACLs, declared capabilities, and feature flags.
- Across the LibreChat host and GlassHive worker boundary, the host is a faithful courier: pass the
  user's goal, constraints, files, available capabilities, and tool results without inventing a
  plan, provider/tool list, rubric, success criteria, or forced artifact. Harness/runtime owns
  reliable data in/out, authorization, recovery, and observability; models own judgment.
- Do not silently remap configured models/providers, weaken expected outputs to pass checks, or rely
  on stale installed artifacts.
- Do not edit App Support files, database leftovers, or generated outputs and call that a product
  fix.
- Prompt or model-behavior changes must use Prompt Workbench and follow
  `docs/requirements_and_learnings/49_Prompt_Architecture_and_Token_Efficiency.md`. Inspect the
  owning source and source -> rendered/compiled -> live lineage; run the same sanitized positive,
  negative, and adjacent cases old versus proposed on the exact configured models before real-user
  QA. Do not add hidden inline prompt fallbacks that Workbench cannot show, version, and evaluate.
- Update the owning requirements doc when product truth changes.
- For local prod/dev runtime boundaries, restore/continuity decomposition, and shipped-artifact
  classification, follow the owning docs rather than duplicating those procedures here.
- Before agent-sync work, read `viventium_v0_4/LibreChat/AGENTS.md` and follow its A/B/C drift and
  dry-run contract.

## Verification Contract

- Automated tests prove deterministic code and contracts; Prompt Workbench exact-model evals
  provide evidence for model behavior; real-user QA proves the delivered experience. These are
  separate gates; none substitutes for another.
- Match verification to the actual blast radius. Run the smallest relevant automated checks, but
  run them. Do not add browser, voice, release, or clean-machine ceremony to a docs-only change.
- For user-visible behavior, exercise the real affected surface. Browser-facing work requires a real
  browser; voice/audio work requires the delivered or audible path; installer/runtime work requires
  the generated and active artifact.
- Use the owning QA feature inventory and natural user use cases when a product feature changes. Cover the
  applicable happy path, failure/degraded state, recovery, persistence/reload, cross-surface parity,
  generated/shipped artifact verification, and public/private safety.
- For a completion or release claim, connect
  `feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`.
  Inspect owning code, docs and nested docs, scripts/harnesses, logs, DB/state/persistence,
  generated/shipped artifacts, and the real user path where applicable.
- If a required real user path cannot run, report `BLOCKED` or `PARTIAL` and name the missing
  prerequisite. Mocks, source inspection, tests, logs, DB rows, API responses, or model review are
  supporting evidence, not substitutes for any required visible-UI, detail-state, persistence, or
  wording step. Supporting evidence cannot replace required user-path evidence.
- Distinguish an empty result from provider unavailable, timeout, rate limit, auth/config missing,
  request rejected, unsupported configuration, and missing local prerequisites such as Docker.
- For architecture, security, forensic, or release decisions, form an evidence-backed proposal
  first, then use a review-only independent opinion when available. Give the reviewer the relevant
  evidence and a precise decision to challenge; sanitize private values. Reviewer output supports
  but does not replace tests or user-path evidence.
- Before public release, verify public-safe git identity and scan the staged diff and QA artifacts
  for secrets, private identity, and machine paths.

## Core Commands

- Installer: `./install.sh`
- Public CLI: `bin/viventium`
- Stack launcher: `viventium_v0_4/viventium-librechat-start.sh`
- Local prod status: `bin/viventium dev-runtime status`
- Side-by-side dev: `bin/viventium dev-env create dev` and `bin/viventium dev-env run dev start`
- Promote checkout: `bin/viventium dev-runtime activate-current --validate --restart --allow-protected-folder`
- Release tests: `python3 -m pytest tests/release/ -q`
- Compiler tests: `python3 -m pytest tests/release/test_config_compiler.py -q`
- LibreChat: run `npm run backend:dev`, `npm run frontend:dev`, `npm run test:api`, or
  `npm run test:client` from `viventium_v0_4/LibreChat/`.
- Telegram: run `pytest` from `viventium_v0_4/telegram-viventium/`.
- Voice gateway: run `python3 -m pytest tests -q` from `viventium_v0_4/voice-gateway/`.

Keep this file lean. Put new detail in the owning docs, nested instructions, skills, tests, or hooks.

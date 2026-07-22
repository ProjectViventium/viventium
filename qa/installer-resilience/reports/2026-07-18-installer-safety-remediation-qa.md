# Installer Safety Remediation QA Run - 2026-07-18

## Summary

- Result: **PARTIAL**. Six bounded source defects were narrowed or fixed, but a clean-machine
  Easy Install, full-payload restore, authenticated Feelings discovery, integration lifecycle,
  immutable release bootstrap, and installed-runtime verification remain open.
- Build/source under test: current parent working tree; LibreChat navigation patch applied to a
  disposable worktree created from the parent-locked LibreChat revision.
- Runtime/artifact under test: ephemeral LibreChat production client bundle and temporary loopback
  dev server; shipped universal macOS helper fallback; the established runtime was not restarted or
  replaced, but its Vite source server already serves the modified Feelings hook from the shared
  checkout.
- Environment: local macOS host, isolated temporary source/build directory, anonymous Playwright
  browser, and a temporary Chrome tab controlled through macOS Computer Use.
- Tester: Codex plus an independent read-only agent review and a completed review-only Fable 5
  Extra pass.
- Related change: snapshot/restore truthfulness, transactional headless configuration, existing-checkout
  origin validation, Playground loopback binding, Express prerequisite copy, and Feelings Controls
  discovery.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `INST-004` | PARTIAL | 27 wizard tests pass | Express copy now names Groq, worker sign-in, browser account connection, and skippable options; full journey remains fragmented. |
| `INST-005` | PARTIAL | 29 continuity/helper tests pass; universal helper inspected | Metadata-only capture can no longer masquerade as a recoverable backup, rewrite the last successful snapshot, promote a failed manifest attempt, or be dereferenced as a restore source; full payload restore is unproven. |
| `INST-006` | PARTIAL | 6 config-transaction tests pass | Headless config uses candidate validation, atomic replacement, private backup, and canonical rollback; interactive Keychain writes and derived schedule/helper/process effects are not yet transacted. |
| `INST-007` | PARTIAL | 8 bootstrap tests pass | Accidental wrong-origin, tracked-dirty, and clean local-ahead states are rejected before CLI execution; hostile-repository defense, immutable provenance, hook-safe staging, and journal/resume are not implemented. |
| `INST-008` | BLOCKED | clean-machine journey not run | No disposable clean macOS target was available without risking established state. |
| `INST-009` | FAIL | audit source trace | Configured-only readiness and fragmented next actions remain broader product defects. |
| `INST-010` | BLOCKED | integration lifecycle not run | No synthetic Groq/xAI/Telegram/Google/Microsoft/Slack/WhatsApp account matrix was connected or mutated. |
| `INST-011` | BLOCKED | platform matrix not run | Clean supported macOS, interruption, offline, low-resource, and recovery matrices remain outstanding. |
| `INST-012` | PARTIAL | clean build, 3 hook tests, 20 root contract tests, anonymous browser redirect | Feelings is added to chat Controls under the existing startup gate, but the nested commit is not parent-pinned or installed and authenticated click-through is unproven. |
| `INST-013` | PARTIAL | shell contract and 2 loopback tests pass; live listener inspected read-only | Modern Playground source binds to loopback, but the unchanged running process still listens on a wildcard address; isolated restart and denial probes remain required. |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `INST-UC-001` | Run install/configure/doctor and recover | CLI source and isolated automation | PARTIAL | failure wording asserted | owning scripts, docs, and focused tests | real install/recovery not run |
| `INST-UC-002` | Review public QA evidence | Markdown package and safety scan | PASS | package is readable and status-labeled | scan found no personal path, email, or credential in scoped files | workspace-wide unrelated artifacts still fail release safety |
| `INST-UC-003` | Rerun evidence checks after changes | release and focused suites | PASS | ownership regression fixed on rerun | final expanded suite `978 passed, 7 skipped, 2 unrelated artifact failures`; focused run `91 passed` | unrelated dirty-workspace reports still prevent a completely green full-tree result |
| `INST-UC-004` | Verify default nightly workflow | automated release suite only | PARTIAL | no user-visible scheduler run | owning release tests passed in the broader suite | clean install and live schedule not run |
| `INST-UC-005` | Complete Express and inspect readiness | wizard copy and source trace | FAIL | copy improved, end-to-end setup still not decisive | readiness contradictions remain in audit | implement unified setup health and first-answer journey |
| `INST-UC-006` | Capture and restore before risk | snapshot/helper source and automation | PARTIAL | metadata-only state is explicit and refused by restore | source, helper binary, docs, 29 continuity/helper tests including capture failure and default/explicit restore refusal | disposable full-payload restore |
| `INST-UC-007` | Reconfigure without losing unrelated state | headless isolated config harness | PARTIAL | success/failure behavior asserted | before/candidate/after comparisons and rollback tests | interactive Keychain staging and generated/schedule/helper/process compensation |
| `INST-UC-008` | Bootstrap empty and existing targets | isolated real/fake Git harness | PARTIAL | wrong-origin, dirty, and local-ahead refusals asserted | accepted HTTPS/SSH identity forms and exact remote-revision check | immutable manifest, hook-safe staging, resume, live public URL |
| `INST-UC-009` | Novice one-command to first useful answer | none | BLOCKED | not substituted with automation | clean-machine prerequisite absent | disposable clean macOS target |
| `INST-UC-010` | Compare configured/ready/degraded states | source and docs | FAIL | current journey still overstates readiness | audit finding remains open | shared structured health model and live probes |
| `INST-UC-011` | Connect, test, repair, and revoke accounts | none | BLOCKED | no personal account was touched | integration research and source inventory only | synthetic account matrix |
| `INST-UC-012` | Exercise platform/failure matrix | none | BLOCKED | no owner machine mutation | matrix is documented | isolated machines and network/resource controls |
| `INST-UC-013` | Discover Feelings from chat Controls | anonymous real browser plus clean-build component tests | PARTIAL | signed-out `/feelings` visibly redirects to login and preserves the target | running Vite-served source and ephemeral production bundle contain the control; stale dist and parent pin do not | authenticated control click, back/refresh, disabled gate, pin/build/fresh-install alignment |
| `INST-UC-014` | Prove loopback-only exposure | source contract plus read-only live listener | PARTIAL | no restart or external probe was performed | explicit source host args pass; current running listener is wildcard | isolated restart, loopback/browser/socket proof, second-host probe |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: Easy Install and first-run onboarding safety.
- Requirement: installer/config compiler, public/private boundary, remote-access, stable-runtime, and
  Emotional Cortex requirements.
- Use case: a novice installs safely, connects the minimum account set, reaches a useful answer, and
  discovers Feelings without risking an established user's state.
- QA case: `INST-004` through `INST-013`, especially `INST-UC-006` through `INST-UC-014`.
- Expected result: truthful, transactional, resumable setup with explicit health and an aligned
  source/pin/build/installed artifact chain.
- Actual evidence: focused safety tests and the clean client build pass; the anonymous browser path
  is correct; delivery and clean-machine gates remain incomplete.
- Remaining gap or fix: execute the remaining remediation slices and prove them on disposable
  machines and synthetic accounts before a release-readiness claim.

## Full-View Evidence Checklist

| Evidence surface | Required question | Evidence / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | Requirements 39, 47, and 54; installer cases and checklist rows above. |
| Code owning path | Which code path owns the behavior? | installer/CLI, snapshot/helper, wizard, launcher, config transaction helper, and nested side-nav hook. |
| Docs and nested docs/repos | Which docs or nested repo docs define the expected behavior? | lifecycle inventory, research, remediation plan, requirements 39/47/54, and nested LibreChat ownership trace. |
| Scripts or harnesses | Which scripts, fixtures, QA harnesses, or automated suites exercised it? | focused pytest suites, clean LibreChat build/Jest, shell syntax, Playwright, and Computer Use. |
| Local/external prerequisite state | Which required dependency was proven healthy or degraded? | local API answered on loopback; authenticated browser state and synthetic provider accounts were unavailable. |
| Logs | Which sanitized logs confirm or contradict the result? | anonymous browser: zero console errors; one React Router future-warning; explicit unauthenticated state. |
| DB/state/persistence | Which persisted state confirms it? | personal DB/config was intentionally not read or mutated; isolated config before/after tests prove file rollback only. |
| Generated/shipped artifact | Which artifact was inspected? | ephemeral production client bundle and universal two-architecture helper fallback; current Vite serves patched source, the local client build output is stale, and parent pin/fresh delivery lacks the link. |
| Real user path | Which path was used like a user? | direct `/feelings` in Playwright and Chrome; visible redirect to login with target preserved. |
| Visual/UX comparison | Does visible UX match? | login form is visually coherent, but it provides no authenticated Feelings discovery evidence. |
| Not run / blocked | Which surface was not run? | clean install, full restore, account lifecycle, authenticated control click, live restart/socket probe, and second-host denial. |

## User-Grade Evidence

- Surface exercised: ephemeral clean-build LibreChat frontend in Playwright and a temporary Chrome tab.
- Real user path: an anonymous user navigated directly to `/feelings`.
- Visible outcome: the app redirected to `/login?redirect_to=%2Ffeelings` and showed the Viventium
  login form with email, password, and Continue controls.
- Expanded/detail state: the accessibility tree confirmed the login form and preserved redirect
  target; no account form was submitted.
- Persistence/reload result: not run because authenticated state was unavailable and personal state
  was protected.
- Local/external prerequisite state: loopback API returned healthy configuration; account auth was
  missing by design.
- Evidence retrieval classification, if applicable: auth/config missing for authenticated Feelings
  discovery; clean build and anonymous route were available.
- Fallback path, if applicable: Playwright and macOS Computer Use agreed on the same signed-out path.
- Backend/log/DB confirmation: API availability and browser console were inspected; private DB and
  account state were not used.
- Final model/runtime wording check: no model output was involved; visible login wording did not
  falsely claim Feelings was ready.
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit
  tests are supporting evidence, not substitutes for the still-required authenticated UI,
  persistence, clean-install, and restore paths.

## Automated Evidence

```bash
bash -n install.sh bin/viventium \
  scripts/viventium/restore.sh \
  viventium_v0_4/viventium-librechat-start.sh \
  viventium_v0_4/viventium-local-state-snapshot.sh

uv run --no-project --with pytest --with pyyaml python -m pytest \
  tests/release/test_continuity_audit.py \
  tests/release/test_macos_helper_install.py \
  tests/release/test_config_transaction.py \
  tests/release/test_public_bootstrap_manifests.py \
  tests/release/test_playground_loopback_contract.py \
  tests/release/test_wizard.py \
  tests/release/test_feelings_navigation_contract.py \
  tests/release/test_feelings_contract.py -q -p no:cacheprovider
# 91 passed

npm run frontend:ci
npm run test:ci -- useSideNavLinks.spec.ts --runInBand
# clean pin-based build passed; 3 navigation tests passed

uv run --no-project --with pytest --with pyyaml --with jsonschema \
  --with pydantic --with fastapi --with httpx --with python-multipart \
  --with croniter python -m pytest tests/release/ -q -p no:cacheprovider
# 978 passed, 7 skipped, 2 failed on unrelated dirty-workspace QA artifacts
```

## Findings

- Defects: installed-runtime and delivery alignment are incomplete; readiness and full backup/restore
  remain release-blocking; metadata-only backup ambiguity, headless config non-atomicity, existing
  checkout identity/revision trust, Playground bind ambiguity, Express copy, and Feelings
  discoverability were narrowed in source. Interactive Keychain/config writes and downstream
  schedule/helper/generated/process effects still lack one transaction.
- Regressions: no focused regression detected; release-test ownership initially missed three new
  files and was corrected before final rerun.
- Flakes: none in changed focused suites.
- Environment issues: the first isolated full-suite attempt lacked optional Python dependencies;
  rerun with the documented dependency set completed.
- Residual risks: full restore, interactive Keychain/config transaction and side-effect compensation,
  immutable/hook-safe bootstrap, account/provider lifecycle, clean-machine onboarding, signed-in
  Feelings UX, parent pin, shipped client artifact, installed-runtime restart, and cross-host network
  denial remain unproven.
- Independent Fable reconciliation: the reviewer independently reproduced the pre-fix focused
  aggregate and confirmed the lifecycle, delivery-drift, and release-readiness conclusions. Its new
  restore-pointer finding is fixed and covered by two regressions. Remaining review findings are
  deliberately open: hostile existing repositories are unsafe until hook-safe staging; `INST-013`
  is broader than the Playground-only patch; Feelings merge order is nested commit before parent
  pin/tests; and the direct config helper does not itself provide full schema validation, comment
  preservation, parent-directory fsync, or cross-side-effect transactionality. The bounded
  post-fix review independently reran all 91 focused tests and returned `PASS`; it also identified
  legacy marker-less metadata attempts as a Slice 1 classification gap. See the
  [final review reconciliation](../fable-final-remediation-review-2026-07-18.md).

## Original Request Checklist

| Requested outcome | Status | Evidence / remaining gate |
| --- | --- | --- |
| Full parent and nested history/lifecycle inventory | PASS | Commit ledger, component boundaries, delivery pins, and feature chronology are in the lifecycle inventory. |
| New-machine path versus the established reliable machine | PASS | State-by-state analysis is documented; the clean-machine side is not yet user-grade accepted. |
| Protect personal config/database before risky QA | PASS | This audit boundary verified a private local protective copy outside the public repo; it is not claimed as a product-restorable snapshot. No destructive personal-state QA ran. |
| Secure sandbox and real Mac QA | PARTIAL | Temporary directories, isolated config harnesses, a clean pin-based client worktree, Playwright, and Computer Use were used; no disposable full macOS machine existed. |
| Evidence-backed open-source installer/UI research | PASS | Current popularity, license, security, onboarding, and channel patterns are recorded in the research inventory; no third-party code was copied into the product. |
| Complete happy/unhappy QA design | PARTIAL | The acceptance inventory is complete, but execution is blocked: the release matrix covers first run, auth, degraded dependencies, interruption, retry, restart, restore, accessibility, network, and public/private safety; clean-Mac and synthetic-account execution remain. |
| One-command Express through connected account and first answer | FAIL | This path was not started. Copy is truthful, but account-first onboarding and live readiness are not yet one decisive journey. |
| Telegram, WhatsApp, Slack, Groq, xAI/Grok, LibreChat account boundaries | BLOCKED | Design and research exist for the lifecycle and adapter requirements; no personal or cloud account was connected, changed, or revoked. |
| Feelings flagship navigation | PARTIAL | Source, clean build, focused tests, and anonymous redirect pass; nested pin/build/installed alignment and authenticated use remain. |
| Fable 5 Extra independent challenge | PASS | Final review confirmed the release verdict, found the restore-pointer gap, and the bounded fix was independently rechecked. |
| No cloud changes | PASS | No commit, push, PR, publish, account mutation, or cloud configuration change occurred. |

The request for `100%` coverage is represented as a complete acceptance inventory, not a false
execution claim. The product remains blocked until every applicable clean-machine, account,
integration, restart, restore, artifact-alignment, and network case has real evidence.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.

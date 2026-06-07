# Installer Resilience QA Cases

## Case ID Convention

Use stable `INST-NNN` IDs for installer resilience cases.

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `INST-001` | Install, preflight, doctor, configure, and generated runtime outputs fail honestly and recover cleanly. | User-visible behavior matches source, docs, persisted state, and logs | installer/CLI/helper, generated env, status output | `tests/release/test_config_compiler.py` plus user-grade QA when visible | NOT YET RUN (cataloged 2026-05-17; next feature run required) |
| `INST-002` | Public QA evidence is sanitized and reproducible | A PR reviewer can verify the behavior without private/local data | QA report, git diff, logs summary, generated artifacts | Public-safety scan plus relevant release tests | NOT YET RUN (cataloged 2026-05-17; next feature run required) |
| `INST-003` | Supported installs and upgrades include the default nightly workflow without owner-specific setup. | A new local user gets GlassHive, Prompt Workbench, active nightly reflection, and memory hardening after signing into Codex or Claude. | installer/CLI, preflight, config compiler, generated env, install summary, Workbench seed | `test_default_nightly_routines.py`, `test_wizard.py`, `test_preflight.py`, `test_config_compiler.py`, `test_cli_upgrade.py`, `test_install_summary.py`, `test_prompt_workbench.py` | PASS 2026-05-31 ([report](reports/2026-05-31-default-nightly-workflow-install-upgrade-qa.md)); release suites and temp config simulations proved defaults, worker auth/profile selection, generated env, Workbench seed, summary rows, and no owner identity hardcode; clean separate-Mac install remains a release gate |
| `INST-004` | Express Rich Brain Readiness aligns the installer with the cognitive-system runtime inventory without pretending user-owned integrations are ready. | A new or upgrading user gets the core brain spine automatically, guided setup for user-owned pieces, honest status/readiness rows, and no developer-private defaults. | wizard, preflight, config compiler, install/status summary, generated env, QA map, public examples | `test_brain_readiness.py`, `test_wizard.py`, `test_install_summary.py`, `test_config_compiler.py`, `test_preflight.py`, feature-owner suites as applicable | PARTIAL 2026-05-31 ([report](reports/2026-05-31-express-rich-brain-readiness-implementation.md)); automated registry/wizard/status coverage added, clean-machine browser/onboarding proof remains a release gate |

## `INST-001` - Core User Flow

- Requirement: Install, preflight, doctor, configure, and generated runtime outputs fail honestly and recover cleanly.
- Risk covered: implementation, docs, and user-visible behavior drift apart.
- Preconditions: local Viventium runtime or the specific feature harness is available with synthetic, public-safe data.
- Steps:
  1. Exercise the feature through the real user surface, not only a unit test.
  2. Compare the visible result with source code, generated/runtime config, logs, persisted state, and the owning requirement doc.
  3. Capture a public-safe report with expected result, forbidden result, evidence, residual risk, and follow-up.
- Expected result: the feature behaves as documented and every supporting layer agrees.
- Forbidden result: backend logs, mocks, source inspection, or model completions are treated as full acceptance when a user-visible surface exists.
- Evidence to capture: sanitized visible result, supporting command/test result, generated/runtime state summary, and docs/case links.
- Automation: `tests/release/test_config_compiler.py` plus any narrower feature tests discovered during implementation.
- Last run: NOT YET RUN (cataloged 2026-05-17; not a substitute for the next real feature run).

## `INST-002` - Public-Safe Evidence Record

- Requirement: public QA artifacts must be reproducible and free of secrets, personal data, local paths, raw IDs, and private screenshots.
- Risk covered: a useful local QA run cannot be safely reviewed or published.
- Preconditions: a dated QA report is created for this feature.
- Steps:
  1. Review the report and related diffs for local absolute paths, account identifiers, tokens, raw logs, raw DB rows, private chats, and screenshots with private content.
  2. Keep raw/private evidence outside the public repo and summarize only public-safe counts, statuses, hashes, and conclusions.
  3. Link the report back to this case and the owning requirement doc.
- Expected result: the public report proves the behavior without leaking private/local data.
- Forbidden result: a report includes private transcripts, account identifiers, raw runtime dumps, local home paths, tokens, or secret-bearing command lines.
- Evidence to capture: public-safety scan result and link to the sanitized report.
- Automation: public-safety pattern scan plus relevant release tests.
- Last run: NOT YET RUN (cataloged 2026-05-17; run on each new public report).

## `INST-003` - Default Nightly Workflow Install And Upgrade

- Requirement: Express/Easy, Advanced, and upgrade paths must converge on the supported local
  nightly workflow without hardcoding a developer account or relying on owner-machine leftovers.
- Risk covered: new users install Viventium successfully but do not get the intended nightly
  reflection/memory workflow, or the workflow only works on the original developer laptop.
- Preconditions: synthetic config/temp state can be used; at least one positive worker-auth case
  and one missing-auth case must be exercised without writing private account details to public QA.
- Steps:
  1. Build an Easy/Express config and confirm GlassHive, Prompt Workbench, active Workbench nightly
     seed, and memory hardening are enabled by default.
  2. Run the default-nightly reconciler over an upgrade-shaped config and confirm the same defaults
     are applied once while `operator_user_email` remains empty.
  3. Simulate Codex-ready and Claude-ready machines and confirm an empty generated worker profile is
     filled from the signed-in CLI instead of a hardcoded developer machine value.
  4. Confirm an explicit existing worker profile is preserved even when another CLI is detected.
  5. Simulate no signed-in Codex/Claude CLI and confirm preflight blocks with one clear manual
     action to sign into either worker.
  6. Compile config and inspect generated env for `START_GLASSHIVE`, `START_PROMPT_WORKBENCH`,
     `VIVENTIUM_PROMPT_WORKBENCH_SEED_NIGHTLY_*`, `GLASSHIVE_DEFAULT_WORKER_PROFILE`, and memory
     hardening env keys.
  7. Start or harness Prompt Workbench with a synthetic admin and confirm the built-in
     `Subconscious Deep Thought` schedule is active, `glasshive_host`, and uses the selected worker
     profile.
  8. Inspect install-summary rows and confirm the user sees GlassHive, Prompt Workbench, Nightly
     Reflection, and Memory Hardening status without private account/path leakage.
- Expected result: a supported local user only needs to sign into Codex or Claude if neither worker
  CLI is ready; otherwise install/upgrade compiles a runnable nightly workflow with no owner/private
  identity, raw prompts, local paths, or manual App Support edits.
- Forbidden result: GlassHive or Prompt Workbench is omitted from Express, the nightly schedule is
  inactive by default, an upgrade leaves old configs without the defaults, no-worker auth is reported
  as success, or any public artifact contains a real user email/path/token/raw prompt.
- Evidence to capture: focused release-test results, sanitized generated env key summary, preflight
  item statuses for Codex/Claude/none scenarios, Workbench synthetic seed row, install-summary rows,
  public-safety scan, and Claude review summary when used.
- Automation: `test_default_nightly_routines.py`, `test_wizard.py`, `test_preflight.py`,
  `test_config_compiler.py`, `test_cli_upgrade.py`, `test_install_summary.py`,
  `test_prompt_workbench.py`.
- Last run: PASS 2026-05-31
  ([report](reports/2026-05-31-default-nightly-workflow-install-upgrade-qa.md)); release suites
  and temp config simulations proved defaults, worker auth/profile selection, generated env,
  Workbench seed, summary rows, and no owner identity hardcode. A destructive clean-Mac install
  remains a final public release gate.

## `INST-004` - Express Rich Brain Readiness

- Requirement: Express/Easy, Advanced, and upgrade-shaped configs must converge on the full
  Viventium Cognitive System readiness contract without watering down parity or hardcoding a
  developer machine.
- Risk covered: a new user gets a thin install that omits the brain surfaces running in the mature
  local runtime, or the installer claims readiness while provider auth, transcript source, RAG,
  MCP/OAuth, worker CLI, or optional communications are still pending.
- Preconditions: synthetic config/temp state can be used for automated cases; public evidence must
  not include local account emails, private paths, tokens, transcript text, prompts, screenshots, or
  raw DB payloads.
- Required feature posture matrix:

| Surface | Express/upgrade posture | Required test cases | Feature owner |
| --- | --- | --- | --- |
| Core app/helper | Installed | happy path, restart/status, generated env, public-safety | `qa/installer-resilience/` |
| Scheduler | Installed | service health, DB ledger count, due item, callback proof, restart | `qa/scheduling-cortex/` |
| GlassHive | Mandatory installed | Codex-ready, Claude-ready, neither-ready block, worker profile preservation | `qa/glasshive/` |
| Prompt Workbench | Installed | health, visible schedule, completed run detail, restart | `qa/prompt-workbench/` |
| Nightly reflection | Installed | scheduled prompt -> filled placeholders -> GlassHive run -> callback -> scheduler ledger -> Workbench shows completed | `qa/prompt-workbench/`, `qa/scheduling-cortex/` |
| Memory hardening | Installed | dry-run-first, eligible-user count, disabled-memory skip, power/thermal skip, run state | `qa/memory-hardening/` |
| Transcript ingest | Guided | no folder pending, folder set, missing folder, catch-up/manual ingest, privacy scan | `qa/meeting-transcript-memory/` |
| Conversation Recall/RAG | Guided opt-in | skipped by default, Docker/Ollama missing, enabled health, browser recall answer | `qa/conversation-recall-rag/` |
| Web search | Guided | local Docker path, hosted-key path, missing keys, SearXNG degraded, Firecrawl degraded | `qa/web-search/` |
| Primary AI | Guided required for brain-ready | connected account pending, API-key fallback, post-account connected route | `qa/connected-accounts/` |
| Secondary/fallback AI | Guided optional | skipped visible state, fallback configured, provider failure wording | `qa/connected-accounts/` |
| Voice | Local default on Apple Silicon, hosted-guided elsewhere | local Apple Silicon path, hosted guided path, disabled state, provider auth missing | `qa/modern-playground-voice/` |
| Telegram | Guided | token validation, Keychain-only storage, polling conflict, self-test | `qa/telegram-runtime/` |
| Telegram Codex | Guided separate token | separate token, missing token pending, polling conflict | `qa/telegram-runtime/` |
| Google Workspace MCP | Guided OAuth | pending OAuth, configured endpoint, expired token/action required | `qa/mcp-oauth/` |
| Microsoft 365 MCP | Guided OAuth/Docker | pending OAuth, Docker/prereq missing, endpoint/action required | `qa/mcp-oauth/` |
| WhatsApp | Not available | unavailable wording; no generated config or fake status | `qa/installer-resilience/` |
| Code Interpreter | Off by default | disabled by choice, Advanced/Lab opt-in only, no public default-on example | `qa/code-interpreter/` |
| Skyvern | Off by default | disabled by choice, Advanced/Lab opt-in only, no public default-on example | `qa/installer-resilience/` |
| OpenClaw | Off by default | disabled by choice, Advanced/Lab opt-in only, no public default-on example | `qa/installer-resilience/` |
| Remote access | Off by default | local-only default, guided Advanced opt-in, tunnel state/error public safety | `qa/remote-access/` |

- Steps:
  1. Build Easy/Express configs for no Docker, Docker present, Codex-ready, Claude-ready, and
     neither worker-ready scenarios.
  2. Build Advanced configs that select and skip each guided surface; confirm the same registry
     labels/guidance and no behavior fork.
  3. Run an upgrade-shaped reconciler over existing configs with explicit disables and confirm they
     remain disabled while readiness/status cards are added.
  4. Compile generated env and inspect only public-safe key presence for Scheduler, GlassHive,
     Workbench, nightly reflection, memory hardening, transcript source, RAG, web search, MCPs,
     Telegram, and voice.
  5. Run `bin/viventium status` or the install-summary harness and confirm every core brain surface
     shows `Ready`, `Needs setup`, `Degraded`, `Skipped`, `Disabled by choice`, or `Not available`
     with a concrete next action.
  6. Run feature-owner user-grade QA for any surface whose behavior changed. Browser-facing setup
     or Workbench proof must use a real browser surface before a release-ready claim.
  7. Run public-safety scans over changed docs, examples, QA reports, generated samples, and test
     fixtures.
- Expected result: Express gives the full installed core spine plus honest guided setup for
  user-owned pieces; Advanced exposes the same registry earlier; upgrades preserve user choices; no
  public artifact leaks private data; and no optional/lab feature is falsely enabled by default.
- Forbidden result: GlassHive, Workbench, Scheduler, nightly reflection, or memory hardening are
  omitted from Express; Recall/RAG turns on from ambient Docker without opt-in; the installer invents
  secrets, transcript paths, OAuth grants, or account emails; WhatsApp is advertised without a real
  integration; Code Interpreter/Skyvern/OpenClaw/Remote Access appear default-on; or status says
  ready while a required provider/worker/ledger/callback is pending.
- Evidence to capture: registry coverage test, wizard simulations, generated env assertions,
  install/status rows, scheduler ledger summary, feature-owner case links, public-safety scan, and
  Claude review summary when used.
- Automation: `test_brain_readiness.py`, `test_wizard.py`, `test_install_summary.py`,
  `test_config_compiler.py`, `test_preflight.py`, `test_default_nightly_routines.py`,
  `test_prompt_workbench.py`.
- Last run: PARTIAL 2026-05-31
  ([report](reports/2026-05-31-express-rich-brain-readiness-implementation.md)); automated
  coverage passed. Clean-machine public entrypoint install plus browser first-admin Brain Setup
  remains required before release-ready signoff.

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Installer Resilience. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `INST-UC-001` | On installer/CLI/helper, generated env, status output, verify that install, preflight, doctor, configure, and generated runtime outputs fail honestly and recover cleanly. | owning requirement for `INST-001` / `INST-001` | installer/CLI/helper, generated env, status output | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to INST-001. | User-visible behavior matches source, docs, persisted state, and logs | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
| `INST-UC-002` | On QA report, git diff, logs summary, generated artifacts, create or review the public QA evidence record with setup/auth/config, empty-state, degraded-dependency, and privacy checks. | owning requirement for `INST-002` / `INST-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to INST-002. | The user sees an honest setup, retry, or degraded-state result for INST-002; no fake success is accepted. | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
| `INST-UC-003` | After creating the public QA evidence record, rerun the scan after any retry, report update, or linked artifact change. | owning requirement for `INST-002` / `INST-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to INST-002. | INST-002 remains correct after the persistence or parity step and final wording matches evidence. | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
| `INST-UC-004` | Run an Express/Easy or upgrade-shaped install path and inspect the resulting nightly workflow defaults. | `39_Installer_and_Config_Compiler.md` / `INST-003` | `./install.sh` or `bin/viventium install/upgrade` harness, generated env, preflight, install summary, Workbench synthetic seed | Source, docs, config diff, preflight items, generated env keys, Workbench schedule row, focused release tests, and public-safety scan. | GlassHive, Prompt Workbench, active nightly reflection, and memory hardening are configured for the local installing user; missing Codex/Claude auth blocks with one clear action; no private identity is hardcoded. | PASS 2026-05-31 ([report](reports/2026-05-31-default-nightly-workflow-install-upgrade-qa.md)); clean separate-Mac install remains a release gate |
| `INST-UC-005` | Run Express/Easy and Advanced setup simulations, then inspect status/readiness for every brain surface. | `39_Installer_and_Config_Compiler.md` / `INST-004` | `./install.sh` or wizard harness, generated env, `bin/viventium status`, feature-owner QA surfaces | Registry rows, wizard choices, generated env keys, scheduler DB summary, install/status table, feature-owner cases, public-safety scan. | The core spine is installed; guided surfaces clearly say ready/pending/degraded/disabled/not available with next action; no private defaults or fake integrations appear. | PARTIAL 2026-05-31 ([report](reports/2026-05-31-express-rich-brain-readiness-implementation.md)); automated implementation coverage passed, clean-machine/browser proof remains |

## Release Test Traceability

- `tests/release/test_config_compiler.py`
- `tests/release/test_directory_link.py`
- `tests/release/test_doctor_sh.py`
- `tests/release/test_install_summary.py`
- `tests/release/test_installer_ui.py`
- `tests/release/test_preflight.py`
- `tests/release/test_default_nightly_routines.py`
- `tests/release/test_brain_readiness.py`
- `tests/release/test_prompt_workbench.py`
- `tests/release/test_shell_init.py`
- `tests/release/test_wizard.py`

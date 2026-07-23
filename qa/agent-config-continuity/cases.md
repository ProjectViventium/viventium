# Agent Config Continuity QA Cases

## Case ID Convention

Use stable `AGCFG-NNN` IDs for agent config continuity cases.

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `AGCFG-001` | Agent edits, source sync, and reload preserve user-visible configuration without silent field loss. | User-visible behavior matches source, docs, persisted state, and logs | Agent Builder, sync review, Mongo/source/generated config | `tests/release/test_agent_sync_review_contract.py` plus user-grade QA when visible | BLOCKED; cataloged 2026-05-17 and awaiting the next real feature run |
| `AGCFG-002` | Public QA evidence is sanitized and reproducible | A PR reviewer can verify the behavior without private/local data | QA report, git diff, logs summary, generated artifacts | Public-safety scan plus relevant release tests | BLOCKED; cataloged 2026-05-17 and awaiting the next real feature run |
| `AGCFG-003` | Web Search capability state matches runtime/provider readiness | Agent Builder, source/live/generated config, persisted agent state, status output | sync compare, generated config inspection, browser UI, logs/state | FAIL; escaped 2026-05-18 and config-capability rerun pending |
| `AGCFG-004` | Deferred tool configuration survives sync and discoveries bind in the same invocation without cross-request leakage. | Recall stays eager while large operational schemas remain available on demand. | source/live agent config, sync compare, event-driven tool binding | sync and binding regressions plus live compare/reload | PARTIAL 2026-07-11; automated sync/binding regressions pass, live sync/reload proof pending |
| `AGCFG-005` | Every channel preserves an eager GlassHive gateway and scoped deferred discovery without semantic prompt guards. | Short and long requests can launch or check GlassHive from web, channel, and voice without a false unavailable claim. | source/fixture agent config, LibreChat web, isolated channel, Modern Playground voice, MCP/logs/state | release/Jest regressions plus isolated cross-surface QA | PARTIAL 2026-07-13; automated gateway/discovery regressions pass, dedicated isolated-channel parity NOT RUN |
| `AGCFG-006` | The first verified administrator remains the canonical built-in-agent owner across restart and later administrators. | Existing and new users keep the intended main/background agents without ambiguous ownership, startup failure, or silent reassignment. | Native first-admin state, source managed baseline, Mongo users/agents/ACLs, restart | Native script/helper regressions plus LibreChat seed regressions and exact-payload user QA | PARTIAL 2026-07-22; automated exact-ID/mode/EPERM/seed/helper regressions pass, replacement exact-payload multi-admin restart NOT RUN |
| `AGCFG-007` | A first upgrade from every retrievable public LibreChat pin migrates built-ins without overwriting user edits, including when no local managed baseline exists. | Existing users receive the current managed defaults while their intentional main/background agent changes survive; interrupted or tampered migrations fail closed and retry safely. | parent component history, nested migration registry, protected App Support handoff, seed baseline, upgrade rollback | `tests/release/test_agent_migration_state.py`, `tests/release/test_managed_agent_migration_history.py`, `tests/release/test_cli_upgrade.py`, and LibreChat seed regressions | PARTIAL 2026-07-22; automated 74-lock-revision/62-retrievable-pin/22-baseline-group, frozen post-pin history audit, protected-state retry/tamper, and actual shipped-CLI ledger-discovery checks pass; real established-user browser/DB upgrade remains NOT RUN |

## `AGCFG-001` - Core User Flow

- Requirement: Agent edits, source sync, and reload preserve user-visible configuration without silent field loss.
- Risk covered: implementation, docs, and user-visible behavior drift apart.
- Preconditions: local Viventium runtime or the specific feature harness is available with synthetic, public-safe data.
- Steps:
  1. Exercise the feature through the real user surface, not only a unit test.
  2. Compare the visible result with source code, generated/runtime config, logs, persisted state, and the owning requirement doc.
  3. Capture a public-safe report with expected result, forbidden result, evidence, residual risk, and follow-up.
- Expected result: the feature behaves as documented and every supporting layer agrees.
- Forbidden result: backend logs, mocks, source inspection, or model completions are treated as full acceptance when a user-visible surface exists.
- Evidence to capture: sanitized visible result, supporting command/test result, generated/runtime state summary, and docs/case links.
- Automation: `tests/release/test_agent_sync_review_contract.py` plus any narrower feature tests discovered during implementation.
- Last run: BLOCKED; cataloged 2026-05-17 and not a substitute for the next real feature run.

## `AGCFG-002` - Public-Safe Evidence Record

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
- Last run: BLOCKED; cataloged 2026-05-17 and required on each new public report.

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Agent Config Continuity. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `AGCFG-UC-001` | On Agent Builder, sync review, Mongo/source/generated config, verify that agent edits, source sync, and reload preserve user-visible configuration without silent field loss. | owning requirement for `AGCFG-001` / `AGCFG-001` | Agent Builder, sync review, Mongo/source/generated config | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to AGCFG-001. | User-visible behavior matches source, docs, persisted state, and logs | BLOCKED; cataloged 2026-05-18 and awaiting the next real feature run |
| `AGCFG-UC-002` | On QA report, git diff, logs summary, generated artifacts, create or review the public QA evidence record with setup/auth/config, empty-state, degraded-dependency, and privacy checks. | owning requirement for `AGCFG-002` / `AGCFG-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to AGCFG-002. | The user sees an honest setup, retry, or degraded-state result for AGCFG-002; no fake success is accepted. | BLOCKED; cataloged 2026-05-18 and awaiting the next real feature run |
| `AGCFG-UC-003` | Compare Agent Builder's Web Search enabled state against generated config and actual provider readiness after a search failure. | `docs/requirements_and_learnings/37_LibreChat_v083_Config_Alignment.md` / `AGCFG-003` | Agent Builder browser UI, sync compare, generated config, status output | Live agent state, source-of-truth bundle, generated LibreChat YAML, provider health/status, persisted tool-call state | Capability UI, runtime config, and provider readiness are either all healthy or the degraded gap is explicit before user-facing search claims. | FAIL; escaped 2026-05-18 and rerun pending |
| `AGCFG-UC-004` | Ask Viv to recall history and then use a deferred operational tool in the same turn after agent sync/reload. | `37_LibreChat_v083_Config_Alignment.md` / `AGCFG-004` | Chrome chat, agent compare/sync, runtime logs | A/B/C drift, prompt-frame tool counts, binding logs, visible tool result | Recall stays available eagerly and the discovered operational tool works in the same invocation without another request's tools leaking in. | PARTIAL 2026-07-11; automated coverage passes, live proof pending |
| `AGCFG-UC-005` | Send one synthetic long GlassHive request followed by a terse status request through an isolated channel, then repeat the launch/status contract in isolated web and voice surfaces. | `03_Telegram_Bridge.md`, `07_MCPs.md`, `37_LibreChat_v083_Config_Alignment.md` / `AGCFG-005`, `TR-008`, `MPV-014` | isolated channel, browser, Modern Playground call | provider-bound tool names, `tool_search`/tool calls, visible and audible results, fixture content parts, GlassHive run/events, runtime logs, restart/reload evidence | All three channels expose the eager launch/status/wait gateway; deferred tools remain discoverable in the same invocation; no channel claims GlassHive is unavailable while the server is healthy. | PARTIAL 2026-07-13; automated structural gateway/discovery tests pass, isolated three-surface proof NOT RUN |
| `AGCFG-UC-006` | Complete first admin setup, add a second synthetic administrator, restart, and open the shipped main agent. | `39_Installer_and_Config_Compiler.md` / `AGCFG-006`, `INST-027` | exact Native payload and supported source Easy Install, browser, Mongo/ACL state | protected first-admin state, managed baseline, exact user lookup, agent authors, owner ACLs, restart logs | The original verified administrator remains the owner; startup succeeds; no administrator scan or silent owner rewrite occurs; invalid protected state gives recovery guidance. | PARTIAL 2026-07-22; automated deterministic script/seed regressions pass, replacement exact-payload browser/restart proof NOT RUN |
| `AGCFG-UC-007` | Upgrade an existing install whose built-ins are unchanged, repeat with one synthetic user edit, interrupt once, and then start/retry. | `39_Installer_and_Config_Compiler.md` / `AGCFG-007` | supported source upgrade CLI, startup seed, Agent Builder browser UI | component refs, protected pending state, registry hashes, baseline/agent DB state, rollback/start logs | Unchanged managed fields advance, the synthetic edit survives, the one-time handoff is consumed only after successful agent/ACL/baseline writes, and retry neither drifts nor loses state. | PARTIAL 2026-07-22; automated deterministic history/state/reconciliation coverage passes, real established-user browser upgrade remains NOT RUN |

## `AGCFG-007` - First-Upgrade Managed Baseline Migration

- Audit all 74 public `components.lock.json` revisions from the reviewed April 2, 2026 support floor:
  62 retrievable nested pins resolve to 22 managed-baseline groups; three historical lock entries are
  explicit tombstones because their nested objects were never published.
- `--check` must work in a standalone LibreChat checkout and re-resolve all 62 predecessor objects;
  full parent-history regeneration additionally requires an explicit exact parent repository root.
  Parent verification is anchored to the artifact's recorded last-lock boundary, not moving branch
  HEAD, and therefore remains stable when the parent later publishes the new nested pin.
- The exact previously shipped CLI does not write a predecessor marker. On its first upgrade into a
  baseline-aware release, startup must derive the prior nested commit from the runner-hash-verified
  upgrade ledger, bind it to the current successor and registry, and record a private one-time
  transaction receipt so later starts cannot recreate a consumed migration.
- Carry the exact pre-pull and post-bootstrap source identities through an owner-only mode-`0600`
  App Support record bound to the target bundle, registry, and upgrade transaction. Never place this
  evidence in generated runtime environment files or accept it from ambient environment variables.
- Reuse an existing pending record only when every bound value is identical. Reject a different
  transaction, successor, bundle, registry, unsafe file, or tampered content without replacing it.
- Retain pending state after seed failure, consume it durably only after all agent, ACL, and baseline
  writes succeed, and let transaction rollback restore the exact pre-upgrade state.
- Expected: every supported existing user advances prior-unchanged built-ins and preserves intentional
  edits on the first baseline-aware upgrade, including background runtime repair.
- Forbidden: owner-machine leftovers, generated-env handoff, silent overwrite, unknown predecessor
  acceptance, partial consumption, or claiming user-path completion from automated evidence alone.
- Automation: `tests/release/test_agent_migration_state.py`,
  `tests/release/test_managed_agent_migration_history.py`, `tests/release/test_cli_upgrade.py`, and
  `viventium_v0_4/LibreChat/api/test/scripts/viventium-seed-agents.test.js`.
- Last run: PARTIAL 2026-07-22. Automated historical regeneration, standalone verification,
  protected-state safety/retry, and an actual synthetic old-CLI process crossing into the new
  start/reconciliation/one-time-consume path pass. A real established-user browser/DB upgrade and
  rollback/retry journey is NOT RUN.

## `AGCFG-006` - Durable Canonical Built-In Agent Owner

- Resolve and store only a real non-placeholder administrator ID; never persist an email or a
  placeholder owner as canonical state.
- On every later Native start, read an owner-owned mode-`0600` regular state file and query that
  exact ID. On source starts, prefer the validated local baseline owner and then the verified
  existing built-in main-agent owner before single-admin inference.
- Add a second synthetic administrator and prove restart neither scans for a replacement nor
  changes the stored owner, built-in authors, or owner ACLs.
- Upgrade a historical closed first-admin state that has no owner ID after a second administrator
  exists; recover only from the exact shipped main-agent author, retain historical state fields,
  avoid administrator enumeration and Agent/ACL writes, and prove a repeated start is byte-stable.
- Corrupt permissions or the stored ID, delete/demote the recorded administrator, and prove startup
  fails closed with restore/promote guidance while preserving the original state bytes.
- Expected: one stable owner across install, restart, and upgrade; the user retains the configured
  main/background agent system without ambiguity.
- Forbidden: query-order ownership, overwrite on multi-admin restart, placeholder ownership,
  log-only failure with no recovery direction, or treating focused tests as exact-payload proof.
- Last run: PARTIAL 2026-07-22. Automated Native exact-owner preservation, legacy closed-state
  canonical-author recovery, deleted/demoted production-filter rejection, closed-state health/doctor
  recovery wording, exact verification, unsafe-state rejection, zero-write author-conflict
  preflight, CLI/helper recovery guidance, and
  source managed-owner persistence pass deterministic regressions. The universal prebuilt helper is
  rebuilt and hash-aligned, but the
  signed/replacement exact-payload multi-admin browser and DB restart journey remains NOT RUN.

## `AGCFG-003` - Web Search Capability State Must Match Runtime Readiness

- Requirement: `docs/requirements_and_learnings/37_LibreChat_v083_Config_Alignment.md` and
  `docs/requirements_and_learnings/10_Open_Source_Web_Search.md`.
- Risk covered: Agent Builder shows Web Search enabled, but runtime providers are unavailable after a
  user asks Viventium to look something up and QA treats the checkbox as proof that search is usable.
- Preconditions: local runtime running; selected agent has Web Search capability enabled; generated
  config and status output are available.
- Steps:
  1. Open Agent Builder in a real browser and record whether Web Search is enabled.
  2. Compare live agent state with source-of-truth agent bundle, generated LibreChat config, and
     runtime status/preflight for search providers.
  3. Trigger or inspect a synthetic search request and verify persisted `web_search` tool-call parts
     plus provider health/log class.
  4. Record whether the UI should say enabled, degraded, or action required.
- Expected result: capability state, generated config, provider health, and visible answer agree.
- Forbidden result: the Web Search checkbox is treated as proof of successful live search while
  SearXNG/Firecrawl or hosted providers are unavailable.
- Evidence to capture: sanitized browser observation, source/live/generated config diff, provider
  health status, persisted tool-call part counts, and API log failure/source summary.
- Automation: `tests/release/test_agent_sync_review_contract.py`,
  `tests/release/test_config_compiler.py`, and user-grade browser QA.
- Last run: FAIL; escaped 2026-05-18 and config-capability rerun pending.

## `AGCFG-004` - Request-Scoped Deferred Tool Binding

- Compare source, live, and pending agent state before sync; verify `tool_options` is protected.
- Keep `file_search` eager and mark bulk operational tools `defer_loading: true`.
- Discover a deferred tool and use it in the same event-driven invocation; overlap two requests with
  different discoveries and confirm neither receives the other's tools.
- Reload the runtime and repeat the compare.
- Expected: token-heavy schemas remain deferred, discovered tools bind immediately in request scope,
  and compare/sync/reload preserves the structured options.
- Forbidden: prompt-text/agent-name routing, next-turn-only discovery, shared mutable binding, or a
  default push over unreviewed live drift.
- Evidence: source/live/generated A/B/C compare, dry-run, sync tests, binding tests, runtime logs.
- Last run: PARTIAL 2026-07-11; automated coverage passes, live compare/reload proof pending.

## `AGCFG-005` - Cross-Surface GlassHive Gateway Parity

- Compare source, live, and pending agent state before sync; verify only the reviewed gateway/tool
  instruction changes are pending.
- Preserve `workspace_launch`, `workspace_status`, and `workspace_wait` as eager definitions on every
  Agents-pipeline surface; keep the remaining operational schemas deferred.
- Remove semantic Telegram keyword/length gates. Only structural capability, OAuth, server-health,
  and explicit configuration state may limit tool availability.
- For a needed deferred GlassHive operation, require scoped `tool_search` and same-invocation use.
- Replay the exact long-then-short Telegram incident shape, then run equivalent web and audible voice
  journeys with synthetic public-safe work.
- Expected: the connected server, provider-bound gateway, actual tool call, visible/audible result,
  Mongo tool content, GlassHive run state, logs, and latency all agree.
- Forbidden: MCP UI registration is treated as execution proof; a short turn receives zero agent/MCP
  definitions; the model reports GlassHive unavailable without scoped discovery or an explicit server
  error; supporting logs/tests substitute for a required real surface.
- Evidence: A/B/C compare, dry-run and reload, provider-binding logs, Mongo content-part counts,
  GlassHive SQLite/events, sanitized screenshots/transcripts/audio observation, restart persistence,
  and p50/p95 timing where the harness supports repeated runs.
- Last run: PARTIAL 2026-07-13; automated eager/deferred binding and failure-state
  regressions pass. A dedicated isolated channel/web/voice replay is NOT RUN.

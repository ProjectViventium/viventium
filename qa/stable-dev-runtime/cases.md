# Stable Dev Runtime Cases

## SDR-001: Dev Env Uses Separate App-Facing Ports

- Requirement: `50_Stable_Dev_Runtime.md`
- Surfaces: CLI, generated config
- Preconditions: canonical config exists
- Steps: run `bin/viventium dev-env create dev --port-offset 1000`, then inspect the dev config
- Expected Result: LibreChat API, frontend, playground, and voice health ports are offset
- Forbidden Result: heavy singleton service ports are unnecessarily offset or duplicated
- Evidence: dated report under `reports/`
- Last Run: 2026-05-14 local implementation QA - passed

## SDR-002: Singleton Services Are Not Duplicated By Default

- Requirement: `50_Stable_Dev_Runtime.md`
- Surfaces: CLI, compiler, launcher
- Preconditions: dev env exists with default shared singleton policy
- Steps: compile the dev env and inspect generated runtime env
- Expected Result: shared singleton markers are present and start flags for shared services are false
- Forbidden Result: dev start launches duplicate recall/RAG, SearXNG, Firecrawl, Google MCP, or MS365 MCP by default
- Evidence: dated report under `reports/`
- Last Run: 2026-05-14 local implementation QA - passed

## SDR-003: Activate Current Uses Runtime Checkout

- Requirement: `50_Stable_Dev_Runtime.md`
- Surfaces: CLI, helper config
- Preconditions: developer checkout is valid
- Steps: run `bin/viventium dev-runtime activate-current --validate --allow-protected-folder`
- Expected Result: existing runtime-checkout state is updated; no code is copied into an install path
- Forbidden Result: parallel active checkout state, physical source copy, or unreviewed nested repo pin change
- Evidence: dated report under `reports/`
- Last Run: 2026-05-14 local implementation QA - passed by live activation, validation, and restart

## SDR-004: Upgrade Check Is Side-Effect-Free

- Requirement: `50_Stable_Dev_Runtime.md`
- Surfaces: CLI, helper
- Preconditions: git checkout with upstream
- Steps: run `bin/viventium upgrade --check --json`
- Expected Result: JSON reports update status and blockers without fetch/pull, Git metadata writes,
  App Support creation, compile, helper install, or restart; exit `0`, `2`, or `3` matches the
  structured result
- Forbidden Result: `FETCH_HEAD`, working tree, App Support, generated runtime files, helper bundle,
  or running stack changes
- Evidence: dated report under `reports/`
- Last Run: 2026-07-19 automated local-remote and no-App-Support regressions - passed; post-change
  headed helper modal rerun remains open

## SDR-005: Helper Update Modal Shows Blocked State Clearly

- Requirement: `50_Stable_Dev_Runtime.md`
- Surfaces: macOS helper, CLI
- Preconditions: helper is installed from the current checkout
- Steps: open Advanced > Check for Updates while the checkout has local QA edits
- Expected Result: modal reports update is blocked with a clear dirty-checkout reason and does not install or restart
- Forbidden Result: silent pull/install, ambiguous error, or helper quits while checking
- Evidence: dated report under `reports/`
- Last Run: 2026-07-19 source/prebuilt and parser regressions - passed; the last headed native modal
  evidence is 2026-05-14 and must be rerun for release acceptance

## SDR-006: Helper Prompt Workbench Stop Is Runtime-Safe

- Requirement: `50_Stable_Dev_Runtime.md`
- Surfaces: macOS helper, CLI, local process state
- Preconditions: helper is installed from the current checkout
- Steps: start Prompt Workbench through `bin/viventium prompt-workbench start`, then use or inspect
  `Advanced > Prompt Workbench > Stop`
- Expected Result: only the managed Prompt Workbench web process stops; the main Viventium runtime
  keeps its current running/stopped state
- Forbidden Result: `bin/viventium stop`, native stack stop, LibreChat stop, or arbitrary port-kill
  behavior from the Prompt Workbench submenu
- Evidence: dated report under `reports/`
- Last Run: 2026-05-15 local CLI/helper integration QA - passed

## SDR-007: Status Summary Is Truthful When Optional Runtime Surfaces Are Down

- Requirement: `50_Stable_Dev_Runtime.md`, `45_Runtime_Feature_QA_Map.md`
- Surfaces: CLI status, generated runtime config, macOS helper state
- Preconditions: core web surfaces are running; one or more enabled optional surfaces are unreachable
- Steps: run `bin/viventium status`, inspect generated runtime env/config, and verify the helper process when `showInStatusBar` is enabled
- Expected Result: status headline is "needs attention"; core surfaces are Running; each enabled but unreachable optional service is Action Required; helper status is shown separately and truthfully
- Forbidden Result: status says "ready" while enabled recall/search/MCP/helper surfaces are broken, or shows "still starting" because of a stale start lock
- Evidence: dated report under `reports/`
- Last Run: 2026-05-17 live runtime sanity - passed

## SDR-008: Helper Steady-State Health Checks Stay Lightweight

- Requirement: `50_Stable_Dev_Runtime.md`, `viventium_v0_4/docs/VOICE_CALLS.md`
- Surfaces: macOS helper, modern playground, helper-launched logs
- Preconditions: installed local-prod runtime is running with the modern playground enabled
- Steps: inspect the helper source/test contract, load the modern playground health route, and compare
  helper/start logs before and after a steady-state observation window
- Expected Result: helper status refreshes share one health snapshot per tick, the playground probe
  uses `/api/health` instead of `/`, steady-running checks back off, and helper-launched stack logs are
  rotated on new starts when oversized
- Forbidden Result: recurring helper `GET / 200` root-page probes, duplicated health probes per refresh
  cycle, unbounded helper-start log growth, or any recommendation to stop local prod/Docker as the
  durable product fix
- Evidence: dated report under `reports/`
- Last Run: 2026-05-27 implementation QA - passed with live helper refresh

## SDR-009: Failed Activation Validation Does Not Restart The Stack

- Requirement: `50_Stable_Dev_Runtime.md`
- Surfaces: `bin/viventium dev-runtime`, config compiler, doctor, running local services
- Preconditions: local prod is healthy and an intentionally invalid synthetic config is available
- Steps: record API and Workbench PIDs, run `dev-runtime activate-current --validate --restart`
  against the invalid config, then compare PIDs and health
- Expected Result: command exits nonzero at compilation or doctor, explains that the running stack
  was not restarted, and leaves both PIDs/health unchanged
- Forbidden Result: failed validation continues into a delayed stop/restart or masks compiler failure
- Evidence: release regression plus dated feature QA report
- Last Run: 2026-07-11 local unhappy-path QA - passed; compiler failure returned 1 and both PIDs stayed unchanged

## SDR-010: Upgrade Safety Is Structured And Honest

- Requirement: `50_Stable_Dev_Runtime.md`, `39_Installer_and_Config_Compiler.md`
- Surfaces: public CLI, managed component checkouts, continuity audit, macOS helper
- Preconditions: synthetic clean, refresh-required, dirty, malformed, running, and stop-failure
  states are available
- Steps: run `upgrade --check --json`, then exercise the mutating upgrade guard in isolated fixtures
- Expected Result: clean pin differences are refreshable; dirty selected work returns `3`; unselected
  dirty work does not block; running/no-restart, bad baseline, and stop failure abort before unsafe
  mutation; helper preserves valid blocker detail
- Forbidden Result: exit `0` with blockers, fetch during check, dirty component mutation, swallowed stop
  failure, auto-restart after continuity error, or wording that claims partial state was rolled back
- Evidence: `test_stable_dev_runtime_workflows.py`, `test_cli_upgrade.py`, rebuilt universal helper
- Last Run: 2026-07-19 - passed 84/84 across the two complete affected modules; live no-share guest
  running/no-restart and dirty-selected-component refusal also passed without stopping core services;
  successful/late-failure and headed helper-dialog lanes remain open

## SDR-011: Helper Reconciles Late Runtime Death Without Restart Storms

- Requirement: `50_Stable_Dev_Runtime.md`, `39_Installer_and_Config_Compiler.md`
- Surfaces: macOS helper, helper config, detached public CLI launch, local runtime health
- Preconditions: installed helper is running; local prod is first healthy, then stopped
  unexpectedly after the initial login launch window
- Steps: observe core and configured-sidecar recovery, stop Scheduling Cortex after core readiness,
  repeat short-lived failures, select helper Stop, wait through at least one former retry interval,
  then select helper Start
- Expected Result: unexpected core or configured-sidecar death is recovered through the detached
  CLI path; Scheduling Cortex becoming unavailable changes status to `Needs Attention` and triggers
  bounded repair; retry delay grows
  from 15 seconds to a 15-minute cap; five stable minutes clear crash-loop history; Stop/Start
  intent survives helper relaunch and helper reinstall
- Forbidden Result: a permanent one-shot latch, launch every four-second poll, retry backoff that
  resets after a short-lived start, or polling that undoes explicit Stop/Quit
- Evidence: deterministic policy harness, helper build, source/prebuilt hash checks, timestamped
  helper/start logs, process/port evidence, and headed menu-bar Stop/Start/relaunch QA
- Last Run: PARTIAL 2026-07-24; deterministic policy, configured-sidecar repair source contract,
  helper build, and hard-kill installer forward-recovery regressions passed; headed installed-helper
  Scheduling late-death/Stop/relaunch QA remains open

## SDR-012: Checkout Promotion Is Transactional And Crash-Recoverable

- Requirement: `50_Stable_Dev_Runtime.md`
- Surfaces: `dev-runtime activate-current`, generated runtime, active checkout, helper intent,
  running/stopped state
- Preconditions: synthetic prior/candidate runtime outputs and an owner-private activation journal
- Steps: validate a candidate, inject failures after prepared-manifest allocation, live-runtime
  backup, and candidate swap, reject a candidate before publication, exercise restart rollback,
  start from a checkout missing a config-selected optional component and prove it is bootstrapped
  through private sibling staging, exact-pin validated, published without residue, and
  strict-pin/alignment-rechecked before App Support activation state; repeat an unavailable-pin
  failure twice and prove neither attempt creates a reusable default-branch checkout; inject a
  concurrent target at the publication syscall and prove its inode and contents survive; switch
  canonical component selection between gates and prove the bound config digest aborts,
  preserve no-follow component virtual-environment and candidate links through publish,
  rollback, and commit, reject a symlinked App Support ancestor before an absent first runtime can
  allocate anything, exercise begin/status/recovery with a transaction receipt larger than the
  macOS argument limit, mutate the still-live original runtime and checkout during prepared-state
  interruption, launch a synthetic native process whose declared data path contains spaces and
  inspect its exact operating-system argument vector, force restart rollback through the nested
  candidate stop, verify every stop-only helper is defined before its early-exit gate, hand off a
  same-database helper-installed Scheduler across checkout scopes, align the full launcher and
  native stack on one Mongo PID receipt, repeat activation when the candidate already holds the
  exact protected owner environment, atomically rewrite that target to its exact checkpoint inode
  before prepared and published rollback, atomically rewrite it again after healthy candidate
  startup with both identical bytes and a declared runtime-managed port change, keep an
  authoritative predecessor source unchanged
  through final commit-boundary verification, keep helper supervision quiesced throughout the
  pre-commit candidate restart, launch an exact synthetic legacy helper that retains stale
  in-memory supervision, prove activation terminates it transactionally, resurrect it before
  publication and prove publication fails closed, restore its prior running state on rollback,
  diverge owner state concurrently, then inject helper refresh failure/interruption after healthy
  core commit
- Expected Result: helper supervision is quiesced and exactly restorable while candidate
  compiler/doctor/helper-artifact validation runs; no binding/runtime/running-state mutation occurs
  before validation; all config-selected components exist at an accepted pinned/local revision
  before the activation journal or helper mutation; failed bootstrap leaves App Support untouched
  and leaves no final component target or staging residue; atomic no-replace publication preserves
  a concurrent writer, and every preactivation component gate observes one bound canonical-config
  digest; exact legacy helper-process absence precedes the durable transaction token, which is
  followed by an exact managed-field receipt and revalidated before publication; an exact
  tokenless legacy shutdown flush is recoverable only while its managed view and process-absence
  receipt still match, while a plan-only crash or
  concurrent owner intent is preserved; an older helper process is identified by its exact
  owner-controlled bundle executable plus revalidated process-start identity, its exact prior
  running bundle paths are journaled before termination, resurrection blocks publication/commit,
  rollback keeps a retryable pending receipt until those exact bundle processes return, and
  the detached candidate/recovery `start` child inherits an explicit preserve-intent flag while
  ordinary user starts still record `running`; successful activation does not refresh the helper
  until after core commit; transaction allocation cannot leave a manifest-less
  directory; the runtime
  target is revalidated inside canonical App Support before recovery; planned staging/backup paths
  are journaled before the
  first live rename; pre-commit restart failure restores exact prior state; a `core_committed`
  receipt makes the wider helper refresh forward-only and retryable without rolling back the
  accepted runtime/binding; candidate restart does not restore owner helper intent until the
  transaction commits; legitimate nested runtime symlinks are recorded without following
  them, survive exact rollback or committed publication, and leave external targets byte-identical;
  an absent first runtime beneath a symlinked App Support ancestor fails before any external
  manifest, snapshot, transaction, or runtime write; large exact-continuity manifests are streamed
  into parsers and remain recoverable without an `E2BIG` process-launch failure; prepared recovery
  preserves natural same-inode runtime activity and concurrent checkout/owner-environment edits
  that activation did not create while restoring only token-owned helper fields; a byte-exact
  pre-existing owner environment receives a reversible identity receipt; after candidate startup,
  the original artifact is validated independently while the current target passes the semantic
  acceptance gate, so same-content atomic replacement and declared managed-only drift commit while
  protected or unknown drift fails closed; a detached receipt is
  atomically quarantined into a private same-filesystem claim directory only when its identity/digest and
  the restored target checkpoint both match exactly; successful predecessor-source verification
  proceeds to commit while failed verification rolls back; terminal cleanup validates the open
  descriptor, zeroes only a detached single-link inode, and moves the source into bounded
  per-checkout retirement slots without unlinking a possible owner-environment pathname, while a
  racing replacement and crash after either claim remain recoverable without any rename from the
  candidate filesystem into App Support;
  cross-version recovery starts the predecessor
  directly with its own component lock and a one-time inherited global CLI lock; spaced native
  Mongo data paths remain one exact argument, and nested candidate stop inherits internal recovery
  context without recursively recovering the same journal; a same-database installed Scheduler is
  drained for candidate handoff while a foreign runtime identity is untouched, and native Mongo
  restart revalidates the recorded PID, start time, executable/hash/signature, exact arguments, and
  data path plus every PID-file boundary/inode before signalling the process that the native start
  layer actually wrote; a dead stale PID record is pruned as a stopped-runtime no-op
- Forbidden Result: writing `active-checkout.json` or live generated output before validation,
  deferring missing configured-component discovery until candidate doctor after helper quiescence,
  accepting a failed clone's clean default branch on retry, treating refresh-required component
  status as strict activation alignment, replacing a concurrent target directory, accepting a new
  component selection after strict validation,
  ignoring candidate stop failure, deleting a prepared journal without exact helper-intent restore,
  writing the quiescence token before a stale helper has fully exited, leaving a stale helper
  process alive to rewrite quiesced supervision, killing a same-named
  non-Viventium or PID-reused process, accepting a different helper bundle as restoration proof,
  deleting a rolled-back journal before exact helper relaunch is verified, failing to restore a
  previously running helper after rollback, allowing an internal detached candidate start to
  overwrite transaction-owned stopped intent,
  using the candidate component lock to restart the predecessor, attempting core rollback after
  helper ecosystem mutation, following or mutating an external symlink target, accepting a
  symlinked App Support/runtime root or ancestor even when `runtime/` is absent, materializing a
  candidate link target as a regular file/directory, passing a complete activation manifest in
  `argv`, restoring a frozen prepared-state runtime/checkout snapshot over newer owner activity, or
  restoring helper/owner-environment state from a plan without exact ownership evidence, routing
  predecessor recovery through its nested detached launcher, or leaving an unjournaled mixed
  runtime after process loss, splitting a spaced native data path by reparsing `ps` display text,
  deleting an interior empty Linux argument and shifting its following value, reacquiring the outer
  CLI lock during nested rollback stop, or calling a helper that is defined only after the
  stop-only early exit, leaving a secret-bearing materialization receipt after exact rollback,
  deleting one when the restored target differs, failing repeat activation merely because its
  candidate owner environment is already exact, refusing a helper-installed Scheduler after proving it owns the same
  schedules database, killing a foreign Scheduler, or splitting native-Mongo ownership across
  stale launcher and native-stack PID files; a stale/reused PID is never signalled, and an unsafe
  PID-file target cannot stop Mongo before its boundary failure is reported
- Evidence: `tests/release/test_dev_runtime_activation.py`,
  `test_stable_dev_runtime_workflows.py`, source/syntax checks, and a dated public-safe report
- Last Run: PARTIAL 2026-07-24; isolated failure, prepared-helper-intent rollback, atomic
  begin-new allocation, hostile runtime-target rejection, pre-commit rollback, core commit,
  successful helper-supervision merge restoration, detached-child recovery isolation,
  post-commit backup-identity race, forward
  helper-finalization receipt, nested virtual-environment/candidate-link preservation, symlinked
  App Support rejection before first-runtime allocation, and two publish crash points pass. An
  initial live installed-helper promotion failed closed before mutation when a legitimate
  Scheduling Cortex virtual-environment link exposed the missing no-follow manifest lane; the
  synthetic escaped-bug regressions now cover publish, rollback, commit, and all existing
  transaction entry points. The next live attempt reached prepared state and failed closed before
  helper/runtime mutation because its 2.2 MB exact manifest was passed through `argv`; the
  streaming-parser and prepared-preservation regressions now cover that escaped limit and the
  natural live-runtime activity observed before recovery. Transaction-token helper receipts,
  plan-only owner-edit preservation, exact materialization proof, and predecessor direct-start
  handoff are now covered by the isolated activation/workflow gate. A later installed attempt
  exposed a missing config-selected Microsoft 365 component only at candidate doctor; activation
  still failed closed with exact protected-state hashes, and the escaped regression now requires
  atomic no-replace selected-component staging plus config-digest-bound exact clean-pin and
  structured revalidation before App Support activation state. A subsequent installed restart
  reached the native Mongo engine proof and failed closed because display-oriented process text
  split a standard spaced data path. Recovery initially retained the journal rather than guessing
  after its nested stop recursively entered the outer recovery path; exact-argument inspection,
  inherited internal-recovery context, and stop-only helper-order regressions now cover all three
  escaped defects. The real recovery then cleared the journal and restored the protected config,
  helper intent, active binding, and candidate owner-environment absence to their exact pre-run
  state. The next installed restart reached candidate launch, then failed closed because the
  checkout-scoped stop would not drain the same-database helper-installed Scheduler and the full
  launcher read a stale legacy Mongo PID instead of the canonical PID written by native startup.
  Scheduler identity-bound installed-component handoff and receipt-bound native Mongo stop now
  cover both escaped ownership defects, including real-process stop/seal, stale PID no-signal,
  matching legacy PID recovery, Docker no-op, and stopped-runtime no-op cases; rollback again
  restored the same protected hashes. The next retry reached successful native Mongo/Meili and
  sidecar startup, but the health watcher misclassified a recoverable native-fallback warning as
  terminal while its supervised launcher was still alive. Native fallback progress no longer uses
  terminal-failure wording; genuine required-child fatal evidence still wins over wrapper liveness.
  That rollback restored the protected owner `.env` but exposed a separate, exact duplicate
  materialization receipt after a same-content launcher rewrite. No-op env mutators now preserve
  the existing inode, and the commit boundary independently validates and claims the original
  artifact before semantically accepting the current target, including declared managed-only
  updates. Repeat activation also exposed the
  missing receipt path for an already-exact candidate `.env`; prepared/published exact-cleanup,
  repeat-activation receipt, and concurrent-drift refusal regressions now cover both escaped cases.
  The following live candidate reached healthy core surfaces and submitted its detached sidecars,
  but activation recovery treated the intentionally completed wrapper as a stopped runtime.
  Attempt-scoped submission-marker coverage now keeps health polling active after normal wrapper
  exit while preserving explicit-fatal precedence. That same attempt exposed a Telegram cold-start
  race: its 30-second rollback guard was shorter than the launcher's own attach plus readiness
  allowance. The guard is now derived from the full budget plus margin, readiness permits the
  Telegram API's bounded cold/network path, and an attached candidate exit fails immediately.
  Successful installed promotion/restart remains pending.

## SDR-013: Local Checkout Promotion Does Not Require A Cloud Upstream

- Requirement: `50_Stable_Dev_Runtime.md`
- Surfaces: `dev-runtime activate-current`, Git checkout, component lock, helper artifact
- Preconditions: synthetic clean named branch with no upstream plus dirty-parent and dirty-component
  variants
- Steps: run the promotion safety gate from the clean no-upstream branch; add untracked parent work
  and retry; then use only the explicit `--allow-dirty-local-testing` parent-dirty bypass
- Expected Result: the clean local branch reaches the next activation gate without a remote; dirty
  parent or selected-component state fails before App Support creation or `begin-new`; the explicit
  flag bypasses only parent dirtiness and leaves component/helper checks active
- Forbidden Result: requiring a cloud upstream for local promotion, suggesting unsupported
  `--skip-pull` syntax, accepting ambient dirty state, or creating activation state before refusal
- Evidence: executable temp-repo and structural CLI regressions in `test_cli_upgrade.py`, plus
  `test_dev_runtime_activation.py`
- Last Run: PASS 2026-07-24; clean no-upstream, dirty-parent refusal, explicit parent-only bypass,
  and transactional activation regressions passed in isolated fixtures; installed live promotion
  remains the user-path completion gate

## SDR-014: Cross-Checkout Promotion Preserves The Owner Environment

- Requirement: `39_Installer_and_Config_Compiler.md`, `50_Stable_Dev_Runtime.md`
- Surfaces: `dev-runtime activate-current`, ignored `LibreChat/.env`, generated runtime,
  helper-launched future starts, activation rollback
- Preconditions: clean candidate checkouts both without an ignored `.env` and with a byte-exact
  pre-existing `.env`, plus a distinct previous active checkout with synthetic protected,
  owner-secret, unmanaged, and runtime-managed fields
- Steps: promote the candidate; inspect selection order and the staged runtime copy/manifest; permit
  only a runtime-managed field change; inject protected, owner-secret, and unmanaged changes; retry
  with linked/unsafe inputs; delete the declared original-runtime backup at every publication
  phase; inject an owner edit after rollback quarantine and commit acceptance; change the nested
  LibreChat revision after materialization; crash during the transaction-owned materialization
  write; present an independent candidate owner environment; then exercise first and later helper
  starts with a divergent private fallback
- Expected Result: the previous active checkout is authoritative for an established runtime;
  fresh-only sources have explicit/private/candidate precedence; candidate conflicts and
  established missing state fail closed; exact candidate bytes/mode/absence are checkpointed before
  mutation; one revision-bound source snapshot is materialized through a fully written
  transaction-owned hard link and acknowledged by exact inode/digest receipt when the target is
  absent; a byte-exact existing target gains only that transaction-named receipt, while an
  independent target is refused before compile/doctor/publication; a plan-only crash preserves a
  concurrent owner target and retires only an unbound transaction-unique staging file; a detached
  receipt after same-content target replacement is descriptor-validated and zeroed only when its
  single-link count proves it is no longer live, then moved into a bounded per-checkout retirement
  slot. Transaction cleanup never unlinks a pathname that may hold owner-environment value, a
  terminal-window racing replacement is preserved and rejected, repeated promotions do not grow
  residue, and post-commit cleanup failure cannot wedge finalization. Canonical retirement slots
  have fixed checkout-path-independent names and must be zero-byte single-link files; moved
  checkouts accept that state. Recognized digest-suffixed predecessor slots stay byte/inode exact
  through failed activation and rollback, migrate only after core commit, and remain recoverable
  when an older in-progress journal names them;
  the manifest contains only digests; protected auth, owner credentials, empty assignments, and
  unknown fields survive; rollback prevalidates the original runtime backup; forbidden drift
  restores the predecessor without overwriting concurrent owner edits; commit has a durable
  accepted-env boundary and revision proof; a post-acceptance edit forces a real alignment restart
  bound to exact pre/post-health bytes, with the current candidate file as canonical and
  same-content launcher inode replacement permitted
- Forbidden Result: generating new encryption/session secrets merely because the candidate checkout
  is clean, losing connected-account credentials, copying through a link, exposing values in the
  manifest, publishing before staging, committing after protected drift, leaving a secret-bearing
  detached transaction link containing secret-bearing bytes after exact rollback, deleting any possible owner-state
  pathname, deleting that link when target state differs, resurrecting
  a deleted key from the staged predecessor snapshot, or blessing an atomic save that the running
  process did not load
- Evidence: executable owner-environment/source-priority tests in
  `tests/release/test_librechat_owner_env.py`, exact candidate checkpoint/rollback/crash tests in
  `test_dev_runtime_activation.py`, including terminal-window source-swap, detached-secret zeroing,
  bounded-retirement, post-commit forward-progress, semantic allow/deny, and unsafe retirement-state
  regressions; launcher owner-secret continuity, generated runtime inspection,
  pre/post semantic manifests, installed browser session/account persistence, and helper restart
  evidence
- Last Run: PASS-ISOLATED/PARTIAL-INSTALLED 2026-07-24; the full release suite passes
  `1963 passed, 33 skipped`, the frozen affected matrix passes `233`, and an independent
  frozen fresh-clone/focused gate passes `228`. These gates cover legacy rollback,
  stored old-journal recovery, commit-acceptance races, cleanup containment, failed-activation
  legacy non-mutation, shell journal retention, and staged-secret refusal. Installed
  promotion, browser persistence, and helper restart remain completion gates.

## SDR-015: Interrupted Promotion Recovery Uses Canonical State And Degraded-Remote Semantics

- Requirement: `39_Installer_and_Config_Compiler.md`, `47_Remote_Access_and_Tunneling.md`,
  `50_Stable_Dev_Runtime.md`
- Surfaces: `dev-runtime activate-current/status`, detached launcher, App Support runtime state,
  optional-service health
- Steps: interrupt activation after staging, resume from a new CLI process, inject a
  checkout-relative default state root, ANSI-colored nonterminal remote failure, router conflict,
  and a GlassHive MCP without a separate `/health` route
- Expected Result: the exact journaled recovery selection and canonical App Support state are used;
  local API/web/playground/Scheduler/Telegram/voice health can complete while the public edge remains
  visibly degraded; the real GlassHive MCP transport is accepted
- Forbidden Result: guessed staging files, checkout-local Mongo/index state, repeated ten-minute
  rollback loops caused only by router ownership, or an ANSI progress warning treated as fatal
- Evidence: focused release tests, activation journal/status, generated state root, port/health/log
  correlation, and installed retry
- Last Run: PASS-AUTOMATED/PARTIAL-INSTALLED 2026-07-25; 304 affected release tests and the complete
  2,063-passed/11-skipped release suite pass. Final candidate promotion, browser persistence, and
  real channel reply remain required.

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Stable Dev Runtime. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `STABLEDEV-UC-001` | Run the stable dev runtime status/start path and inspect generated runtime config, helper state, and web surface reachability. | `50_Stable_Dev_Runtime.md` / `SDR-001`-`SDR-007` | `bin/viventium status`, dev-runtime/dev-env CLI, helper status, and browser/health endpoints | Generated config summary, status output, helper state, logs, release tests, and dated QA report | Core services and optional services are classified truthfully, with helper status separate from runtime readiness. | 2026-05-17 live runtime sanity - passed for status classification |
| `STABLEDEV-UC-002` | Run the same status path when optional services or helper surfaces are disabled/unreachable. | `50_Stable_Dev_Runtime.md` / `SDR-007` | CLI status, generated runtime config, helper state, and logs | Optional service health, stale lock checks, generated env/config, logs, and QA report | Status says needs attention/action required for unreachable enabled optional surfaces and never masks broken dependencies as ready. | 2026-05-17 live runtime sanity - passed |
| `STABLEDEV-UC-003` | Start and stop Prompt Workbench from the CLI/helper path and verify it does not start or stop the main Viventium runtime. | `50_Stable_Dev_Runtime.md` / `SDR-006` | CLI prompt-workbench lifecycle, helper submenu, health endpoint, process state | PID/port metadata summary, `/api/health`, process state, helper install inspection, and QA report | Only the managed workbench process is affected; LibreChat/main Viventium stack state is preserved. | 2026-05-15 local CLI/helper integration QA - passed |
| `STABLEDEV-UC-004` | Leave local prod running while developing and verify the helper does not continuously render user-facing root pages to decide health. | `50_Stable_Dev_Runtime.md` / `SDR-008` | macOS helper, modern playground `/api/health`, helper-launched logs, real browser route check | Helper source/test contract, Playwright health/root checks, sanitized log counts, live port/process snapshot | Local prod stays up, dev/server logs stop accumulating helper root-page probes, and no singleton service is stopped or duplicated. | 2026-05-27 implementation QA - passed with live helper refresh |
| `STABLEDEV-UC-005` | Promote a checkout with validation enabled while the candidate config or prerequisites are invalid. | `50_Stable_Dev_Runtime.md` / `SDR-009` | `dev-runtime activate-current --validate --restart`, API/Workbench health and PIDs | Compiler/doctor exit, CLI wording, pre/post process identity | Validation fails loudly before stop/restart and the current healthy stack remains untouched. | PASS 2026-07-11; synthetic invalid config returned 1 and pre/post API and Workbench PIDs matched. |
| `STABLEDEV-UC-006` | Check for and attempt an upgrade from clean, refreshable, dirty, running, and continuity-error states. | `50_Stable_Dev_Runtime.md` / `SDR-004`, `SDR-005`, `SDR-010` | CLI JSON/text, helper modal, disposable running runtime | Exit/status JSON, Git metadata, component state, audit status, process health, helper dialog | Inspection is side-effect-free; safe refresh remains available; blockers stop before mutation with specific guidance; no partial state is called rolled back. | PARTIAL 2026-07-19; 84 affected-module regressions, universal helper rebuild/install, and live no-share running/dirty refusal pass; successful/late-failure update and headed helper dialog remain open. |
| `STABLEDEV-UC-007` | Leave the helper open past its login window, simulate a late runtime death, then use Stop, relaunch the helper, and Start. | `50_Stable_Dev_Runtime.md` / `SDR-011` | Installed macOS helper, detached CLI runtime, helper config, ports/processes/logs | Persisted desired state, bounded attempt timestamps, helper/start logs, helper menu status, runtime health | Late death self-recovers without a restart storm; explicit Stop remains stopped across helper relaunch; Start resumes supervised recovery. | PARTIAL 2026-07-24; deterministic policy/source/build QA passed, installed headed lifecycle QA remains open. |
| `STABLEDEV-UC-008` | Promote a clean local candidate branch that intentionally has no cloud upstream while preserving unrelated local work. | `50_Stable_Dev_Runtime.md` / `SDR-013` | `dev-runtime activate-current --validate --restart`, Git/component/helper inspection, active checkout | Pre-mutation structured report, active checkout, transaction state, runtime health | Clean no-upstream promotion is accepted; dirty parent/component state is refused before mutation unless the explicit parent-only local-testing flag applies. | PARTIAL 2026-07-24; executable isolated clean/dirty/bypass gates pass; installed live promotion pending. |
| `STABLEDEV-UC-009` | Promote a clean checkout that has no ignored LibreChat environment, then refresh and restart as the existing user. | `39_Installer_and_Config_Compiler.md`, `50_Stable_Dev_Runtime.md` / `SDR-014` | `dev-runtime activate-current --validate --restart`, browser session/accounts, helper restart, generated runtime | Digest-only owner-env manifests, exact candidate checkpoint, transaction receipt, browser persistence, helper/start logs | Existing login/encryption keys, connected-account credentials, and unknown owner fields survive while declared runtime fields may advance; unsafe, conflicting, missing-established, missing-runtime-backup, revision, or concurrent drift fails closed without overwriting owner state. | PASS-ISOLATED/PARTIAL-INSTALLED 2026-07-24; 402 combined affected regressions and the 181-case final blocker gate pass; installed browser/helper evidence pending. |

## Release Test Traceability

- `tests/release/test_cli_upgrade.py`
- `tests/release/test_detached_librechat_api_watchdog.py`
- `tests/release/test_dev_runtime_activation.py`
- `tests/release/test_detached_librechat_supervision.py`
- `tests/release/test_helper_runtime_intent.py`
- `tests/release/test_librechat_client_defaults.py`
- `tests/release/test_librechat_dev_start_config_sync.py`
- `tests/release/test_macos_helper_install.py`
- `tests/release/test_macos_helper_supervision.py`
- `tests/release/test_native_stack_helpers.py`
- `tests/release/test_stable_dev_runtime_workflows.py`
- `tests/release/test_stack_port_probe_timeouts.py`

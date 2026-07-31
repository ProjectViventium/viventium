# 50. Stable Dev Runtime

## Purpose

Viventium developers need a stable installed runtime while they edit and test Viventium. The product
must support that without copying code into install paths, duplicating heavy local services, or
confusing upstream component boundaries.

## Product Contract

- The normal installed runtime remains the canonical local product runtime.
- `bin/viventium dev-env` creates side-by-side development state under App Support.
- Dev envs separate app-facing surfaces by default:
  - LibreChat API
  - LibreChat frontend
  - Modern LiveKit Playground (`agent-starter-react`)
  - voice health port when needed
- Dev envs also separate per-runtime sidecars that own mutable runtime-local state, including
  Scheduling Cortex.
- The classic `agents-playground` UI is not part of local prod or dev-env defaults. It remains an
  explicit classic-playground opt-in only, so default starts do not spend resources on the old UI.
- Heavy local services are shared singleton services by default:
  - Meilisearch conversation search
  - recall/RAG
  - SearXNG
  - Firecrawl
  - Google Workspace MCP
  - Microsoft 365 MCP
- Shared singleton services must not be duplicated merely because a developer starts a dev env.
- Full isolation is an explicit advanced future mode, not the default.
- A listener on the configured Mongo port is not sufficient persistence readiness. Before reusing an
  existing Mongo process, the native launcher must query the running server's parsed command-line
  options and verify that `storage.dbPath` resolves to the configured Viventium data directory. A
  listener backed by restored, development, or otherwise unexpected state must fail closed instead
  of silently switching the user's conversation and memory history.
- Launcher-managed modern-playground runtimes should prewarm the voice startup API routes before
  starting the voice worker so local users and developers do not pay the first-hit Next.js dev
  compile cost on the call page. These prewarm requests are bounded and warn-only so a stuck dev
  compile does not delay the rest of runtime startup for minutes.
- The macOS helper must not keep the installed local-prod runtime healthy by repeatedly rendering
  expensive user-facing pages. Steady-state helper checks use one shared health snapshot per refresh
  cycle, probe the modern playground through a lightweight `/api/health` endpoint, and back off while
  the stack remains healthy. This keeps local prod running beside dev work without turning the helper
  into a background Next.js page renderer.
- The macOS helper owns a durable desired-state supervisor for local prod, not a one-time login
  launch attempt. A runtime that dies later is relaunched with bounded exponential backoff; repeated
  short-lived recoveries retain crash-loop history until the stack has stayed healthy for a
  stability window. `Stop` and `Quit` persist an explicit stopped intent, and a later helper `Start`
  explicitly resumes supervision. Helper reinstall and upgrade preserve this state with the other
  helper preferences.

## Mental Model For Contributors

Viventium has two local modes that can exist on the same Mac:

- **Local prod** is the installed, user-facing Viventium runtime. It is what the helper starts and
  what normal users should rely on day to day.
- **Dev env** is an optional side-by-side developer runtime. It lets contributors test code without
  stealing the local prod app ports or rewriting installed source paths.

Local prod and dev envs must stay separate at the app boundary and shared at the expensive-service
boundary:

| Surface | Local Prod | Dev Env Default |
| --- | --- | --- |
| LibreChat API | canonical installed port | offset port |
| LibreChat frontend | canonical installed port | offset port |
| Modern LiveKit Playground | canonical installed port | offset port |
| voice health port | canonical installed port | offset port when needed |
| Scheduling Cortex MCP | canonical installed port and scheduler DB | offset port and dev-env scheduler DB |
| Meilisearch conversation search | shared singleton | use local prod singleton |
| recall/RAG | shared singleton | use local prod singleton |
| SearXNG | shared singleton | use local prod singleton |
| Firecrawl | shared singleton | use local prod singleton |
| Google Workspace MCP | shared singleton | use local prod singleton |
| Microsoft 365 MCP | shared singleton | use local prod singleton |

This is intentional. The default developer experience should avoid duplicate memory/search/MCP
services because those consume local resources and can make both runtimes flaky. If a future task
needs full isolation, it must be an explicit advanced path with separate ports, separate state, and
clear QA proving it did not become the default.

## Contributor Quickstart

Use this flow when developing Viventium while keeping the installed local product stable:

```bash
# See which checkout the installed helper/runtime uses.
bin/viventium dev-runtime status

# Create a side-by-side dev runtime with offset app-facing ports.
bin/viventium dev-env create dev

# Inspect what changed before starting it.
bin/viventium dev-env status dev

# Run a command inside the dev env.
bin/viventium dev-env run dev start
```

With the default offset, test the two local runtimes at different user-facing URLs:

| Runtime | Web | API | Playground |
| --- | --- | --- | --- |
| Local prod | `http://localhost:3190` | `http://localhost:3180/api` | `http://localhost:3300` |
| Dev env `dev` | `http://localhost:4190` | `http://localhost:4180/api` | `http://localhost:4300` |

Use local prod for normal installed/runtime QA and Telegram checks. Use the dev env for local code
experiments that should not steal the installed runtime's app-facing ports or state. If the dev env
needs conversation search, recall, search, Firecrawl, Google Workspace MCP, or Microsoft 365 MCP behavior, keep the
shared singleton service owner running; those services are intentionally not duplicated by default.

Use this flow when a local development checkout is ready to become the installed local runtime:

```bash
bin/viventium dev-runtime activate-current --validate --restart --allow-protected-folder
```

Before creating App Support activation state, that command bootstraps every component selected by
the existing canonical config. A missing component is cloned into a private sibling staging
directory, validated at its exact clean declared pin, and only then published with the operating
system's atomic no-replace rename; a failed clone leaves neither a target checkout nor reusable
staging residue, and a concurrent checkout creator is never overwritten. Existing clean local
component branches are preserved by ordinary bootstrap, but activation then applies a separate
strict selected-component gate that rejects missing, dirty, vendored, or wrong-revision checkouts
before structured parent alignment is rechecked. Bootstrap, both strict gates, and alignment are
bound to the same no-follow SHA-256 of canonical config, with a final digest recheck immediately
before App Support activation state. A concurrent config edit therefore fails the attempt instead
of changing the selected component set between gates. A missing optional component cannot make
candidate doctor fail only after helper quiescence, and bootstrap failure leaves config, helper,
runtime, and binding untouched.
The command then allocates its candidate and durable manifest in one transaction and snapshots the
complete helper config. Because an older already-running helper may retain the previous `running`
intent in memory and flush a stale nested supervision object while terminating, activation first
terminates only the exact
owner-controlled Viventium helper bundle executable. PID, executable, and process start identity
are revalidated immediately before signalling so PID reuse cannot target an unrelated process. The
exact helper bundle path or paths that were running are recorded in the private transaction before
termination. Only after exact process absence is proven does activation write and acknowledge its
helper-supervision ownership token. A legacy helper shutdown that drops only that token remains
recoverable when the complete managed view still equals the recorded quiesced receipt and the exact
helper process remains absent; any managed-value difference still fails closed. Every prepared
rollback, published rollback, and interrupted recovery restores those
same bundle paths when they were previously running; a durable pending restoration receipt remains
until their exact processes are visible again. Successful activation refreshes and relaunches the
new helper only after the core commit. A helper process that reappears before
publication or commit fails the activation closed. Compiler, doctor, and helper-artifact failure
restores the exact helper intent and prior helper-process state without changing the active
checkout, live generated runtime, or running stack. Only a validated candidate may proceed beyond
the prepared private activation transaction. The transaction
journals an explicit internal restart flag through the detached `start` child so that
candidate validation and predecessor recovery preserve the transaction-owned helper intent.
Ordinary user `start` still records `running`; only the activation/recovery caller may request this
preservation, and the transaction commit remains the sole pre-refresh owner of intent restoration.
The transaction
journals the planned runtime swap before moving live files; checkout binding, restart, configured
health must succeed before the core activation commits. Pre-commit failure or interruption restores
the prior binding, exact generated runtime, helper intent, and original running/stopped state.
Generated runtime snapshots and rollback manifests preserve owner-controlled symbolic-link entries
without following them. This is required for ordinary component virtual environments such as
Scheduling Cortex's `.venv/bin/python*` links: activation may move those entries only as part of the
canonical runtime directory, and must never read, rewrite, remove, or otherwise mutate an external
link target. Candidate publication must likewise copy link entries as links, verify no-follow
source and staged manifests before publication, and never materialize linked external file or
directory contents. The canonical App Support root, runtime root, and their ancestors must still be
real directories rather than symbolic links, including on a first activation where `runtime/` does
not exist yet.
Activation manifests may be large because exact continuity proofs include no-follow hashes for the
prior generated runtime. Shell orchestration must stream those JSON receipts over standard input;
it must never pass a complete manifest as a process argument or retain an unused full commit
receipt, because macOS can reject the process before recovery with `E2BIG`.
Native Mongo engine proof must inspect exact operating-system process arguments, not reparse the
display-oriented output of `ps`. A standard owner data path containing spaces must remain one
argument and pass the same boundary validation as an unspaced path. Linux `/proc` parsing must
remove only the terminal separator and reject interior empty argument fields rather than shifting
option-value association. Stop-only startup paths may call only helpers defined before their early
exit. Activation rollback must also mark its nested candidate stop as internal recovery and give
it one-use inheritance of the outer CLI operation lock so it cannot recursively recover the same
journal or reacquire that lock.
Cross-checkout restart must drain a helper-installed Scheduling Cortex only after its public-safe
health identity proves it uses the same canonical schedules database; a foreign or older identity
remains untouched. Native Mongo stop must use the running-engine receipt to revalidate the exact
PID, process start time, executable/hash/signature, argument vector, and canonical data path before
signalling it. The source launcher and native-stack helper share the canonical App Support native
Mongo PID record; a matching legacy record may be recovered, but a stale/reused PID must never be
signalled. Separate unverified PID files can make restart try to seal a process it did not stop.
The detached startup wrapper is intentionally finite. Once it emits its attempt-scoped
`Detached Startup Submitted` marker, its clean exit is not a runtime failure: configured surfaces
and watchdogs own the remaining health wait, while explicit fatal evidence from that same attempt
still fails immediately. Telegram cross-checkout handoff uses the same principle. Its rollback
guard must outlive the complete attach plus receive-loop readiness budget with recovery margin;
the readiness wait must recognize candidate process exit immediately instead of trading a safe
cold/network startup allowance for a long genuine-failure delay.
While a transaction remains `prepared`, activation has not renamed the generated runtime or changed
the checkout binding. Prepared rollback therefore verifies the original runtime directory identity
but preserves natural in-place runtime activity and concurrent checkout edits; it restores only
helper-supervision fields proven to be activation-owned and an owner environment proven to be the
exact transaction materialization. Helper quiescence is journaled as `planned` before the helper
file changes, tagged in the file with a transaction-unique token, then acknowledged with the exact
managed-field view. Publication revalidates that token and view. A crash before the write or a
later owner change is preserved rather than guessed over; unrelated helper fields remain
merge-preserved. Owner-environment recovery likewise requires the transaction-unique staging file
and candidate `.env` to be the same planned hard-link inode through publication. A plan alone never authorizes
restoring over a concurrent candidate `.env`; an unbound transaction-only staging file may be
cleaned without touching the owner file.
Successful commit also restores the prior helper-supervision values through a merge that retains
unknown or concurrently added helper fields; the temporary validation `stopped` intent is never
allowed to become an accidental owner-setting change. A requested candidate restart launches
directly while that transaction-owned quiescence remains `stopped`; it must not write the owner's
prior `running` intent before commit and then misclassify its own write as concurrent helper drift.
Installed-helper refresh is a wider host mutation than that core journal owns, so it runs only after
the healthy runtime/binding commit. A private `core_committed` receipt makes helper refresh
forward-only and retryable from the next `start`/`dev-runtime` invocation; helper failure never
pretends to roll back the app bundle, helper scripts, installed scheduling component, login item, or
LaunchAgent. The command does not copy code into an install directory.

Use this flow when checking whether the installed runtime can update safely:

```bash
bin/viventium upgrade --check --json
```

This is read-only. A real update still goes through:

```bash
bin/viventium upgrade --restart
```

Use this flow when opening the local prompt QA surface without touching the main runtime:

```bash
bin/viventium prompt-workbench open
bin/viventium prompt-workbench stop
```

`prompt-workbench stop` is intentionally scoped to the Prompt Workbench web app. It must not stop
the installed Viventium runtime or any shared singleton service.

Prompt Workbench can also be enabled as an optional local-runtime sidecar through
`runtime.prompt_workbench.enabled: true` in the canonical config. When enabled, the compiled runtime
sets `START_PROMPT_WORKBENCH=true`, the stack launcher starts Workbench during Viventium startup, and
a local watchdog restarts it if the loopback app dies. The launcher must not print the authenticated
Workbench URL or token into stack logs; users should open the app through `bin/viventium
prompt-workbench open`, the helper submenu, or the LibreChat account-menu entry. If the user stops
Workbench explicitly, the watchdog respects the local user-stopped marker instead of immediately
reopening it.

The stack-managed Workbench owns its configured canonical loopback port. During startup it may
reclaim that port only from a positively identified `prompt_workbench.app:app` process left by a
different checkout or an untracked prior launch. It must never terminate an unrelated listener.
This keeps a healthy-looking restored/dev Workbench from silently serving stale code while the
active runtime reports the sidecar as ready.

## Do And Do Not

- Do use `dev-env` when you need a side-by-side development runtime.
- Do use `dev-runtime activate-current --validate --restart` when promoting the current checkout to
  the installed local runtime.
- `dev-runtime activate-current --validate --restart` must fail closed before stop/restart when
  config compilation, doctor, or helper-artifact validation fails. A later installed-helper refresh
  failure leaves the already healthy runtime/binding core committed and records forward
  finalization for retry; it must not claim that the wider helper ecosystem was rolled back. A
  missing optional prerequisite such as a required Docker daemon may block validation, but it must
  not schedule a delayed stop of the currently running stack.
- Restart promotion without `--validate` is refused. A running runtime also requires `--restart`;
  generated outputs may not be replaced underneath it.
- The activation journal must declare its staging/backup identities before the first live runtime
  rename. Allocation and initial manifest creation are one tool operation, so recovery never sees a
  manifest-less transaction directory. The journal may target only canonical App Support runtime
  state; automatic recovery revalidates that boundary before any replace or removal. Recovery
  handles interruption before backup, after backup, after candidate swap, after
  binding, during restart, after core commit, and during helper refresh. If the candidate cannot be
  positively stopped, pre-commit rollback fails closed without replacing its live runtime
  directory. Once `core_committed` is durable, rollback is forbidden and only idempotent helper
  forward-finalization may run. Manifesting a canonical generated runtime must record legitimate
  nested component symlinks without dereferencing them so exact rollback works; it must continue to
  reject a symlinked App Support/runtime root or ancestor before creating any transaction,
  snapshot, or runtime output. Candidate staging must preserve nested symlinks, compare its
  no-follow manifest to a stable source manifest, and must not traverse or mutate external targets.
  Multi-megabyte transaction receipts must be streamed into parsers rather than copied into
  `argv`; interrupted prepared-state recovery must remain operable at the same manifest size and
  must not overwrite runtime/checkout changes that the prepared phase never made.
- If pre-commit recovery must resume a previously running checkout from a different Viventium
  version, the current recovery process must hand off directly to that predecessor's `start`
  command. It must pass the predecessor's own component lock and the already-held global CLI lock
  exactly once. Calling the predecessor's detached `launch` wrapper would cause its child `start`
  to reacquire the same lock and strand the restored runtime offline.
- Do use `prompt-workbench open/start/stop/status` for the standalone prompt QA app.
- Do use `runtime.prompt_workbench.enabled: true` when Prompt Workbench should stay up with the
  local Viventium runtime.
- Do verify that the stack-managed Workbench process and state file resolve to the active runtime
  checkout; a loopback health response from another checkout is not sufficient readiness.
- Do keep Scheduling Cortex per-runtime: local prod and each dev env get distinct scheduler DBs and
  distinct MCP ports. The default dev-env scheduler port is biased away from shared singleton ports
  so it does not collide with RAG.
- Do report Scheduling Cortex as running only when `/health` has the expected semantic status,
  service identity, and hash of the configured scheduler ledger. An arbitrary HTTP 200 is not
  readiness. Report Memory Hardening from its dedicated loaded/receipt/run health state rather than
  configuration presence alone.
- Do match each managed sidecar's documented health vocabulary. Scheduling Cortex and GlassHive
  publish `status: ok`; RAG publishes `status: UP`. Upgrade and helper readiness must not require one
  service's literal status from another service, and Scheduling Cortex must retain its service and
  ledger-identity checks when its real `ok` response is accepted. When the compiler omits an
  explicit Scheduler DB path, readiness must derive the same per-runtime default as the launcher.
  GlassHive startup health belongs to its local runtime API/MCP/UI ports; the configured operator
  base URL is a user-facing link origin and may intentionally be a public HTTPS address.
- Do make `SIGINT` and `SIGTERM` terminate the active CLI operation with a non-zero signal status
  after releasing its owned CLI lock. If an upgrade rollback transaction is armed, signal handling
  must run that recovery path with the signal status rather than returning to the interrupted wait
  loop or treating the interruption as success.
- Do keep heavy singleton services shared unless the user explicitly asks for full isolation and QA
  proves the isolation.
- Do keep Viventium-owned Docker singleton services bounded with source-owned memory, CPU, PID, and
  log-rotation defaults; live-only container edits are not a durable product fix.
- Do keep helper-launched stack logs bounded on fresh starts so long-lived local prod runs do not
  accumulate unbounded dev-server output.
- Do treat Meilisearch indexes/tasks as derived conversation-search state and rebuild from Mongo
  only through the supported readiness/sync path.
- Do keep generated runtime state under App Support out of git.
- Do not edit generated App Support files and call that a product fix.
- Do not create a second active-checkout pointer; use the existing runtime-checkout state.
- Do not copy source into install paths to "push" a local build.
- Do not wire helper Prompt Workbench controls to the main `start` or `stop` commands.
- Do not silently pull, reset, or update nested repos from dev-env commands.
- Do not treat dirty local QA state as release-ready.

## Commands

```bash
bin/viventium dev-env create dev
bin/viventium dev-env list
bin/viventium dev-env status dev
bin/viventium dev-env run dev start
```

`dev-env create` copies the canonical config into a named dev App Support directory, offsets only
app-facing ports, and records the shared singleton services in `runtime.dev_env`.

Generated dev-env state lives under:

```text
~/Library/Application Support/Viventium/dev-envs/<name>/
```

That directory is local runtime state, not a tracked source-of-truth surface.

```bash
bin/viventium dev-runtime activate-current --validate --restart --allow-protected-folder
```

`dev-runtime activate-current` is a developer-friendly transactional wrapper over the existing
`runtime-checkout` state. It does not copy source code. It validates an isolated generated-runtime
candidate first, journals and publishes that exact candidate, selects the current checkout,
health-checks the requested restart, refreshes the helper, and commits only after all gates pass.
Because activation promotes the current local checkout and never fetches, a clean named branch does
not need a configured upstream. Before App Support or activation-journal mutation, the command runs
the same no-fetch structured inspection used by upgrade: dirty parent work, dirty/misaligned selected
components, and a stale helper artifact fail closed. `--allow-dirty-local-testing` is the only parent
dirty bypass; it does not bypass selected-component or helper-artifact safety.

Promotion between different checkouts also carries the ignored owner-managed LibreChat environment
transactionally. For an established installation, the previous active checkout's safe `.env` is
authoritative and missing state fails closed; a conflicting candidate `.env` is never adopted. For
a fresh activation only, explicit, private-curated, then candidate state may seed first run.
Freshness requires the absence of canonical config, generated runtime, helper config, data/schedule
state, and install/continuity receipts; missing or corrupt owner pointers never make an established
installation fresh.
`begin-new` checkpoints exact candidate bytes/mode/absence before any mutation. One source read is
revision-bound, staged privately with a digest-only manifest, conflict-checked, and atomically
materialized through a durable transaction-owned hard link before compile/doctor/start when the
target is absent. An existing target must already be byte-exact; repeat activation adds only the
transaction-named hard-link receipt to that unchanged inode, while an independent candidate owner
environment is never overwritten. Both stopped and restarted activation paths verify the binding
before commit. The exact materialization inode/digest is acknowledged in the activation journal
before publication. After candidate startup, commit validates that artifact independently, then
atomically accepts the current `.env` through the semantic manifest so a same-content atomic save
or declared runtime-managed change can advance without weakening protected auth, provider, empty,
or unknown owner fields. The original materialization artifact is moved with no replacement into
a transaction-unique `0700` same-filesystem claim directory and revalidated by its own receipt.
Terminal cleanup never unlinks a pathname that holds or could hold owner-environment data. It opens
and validates the exact inode, zeroes it through that descriptor only when its link count proves it
is detached from live `.env`, then moves the source entry into one of three fixed per-checkout
retirement slots (materialization, owner, and a zero tombstone). A source replacement racing the
terminal move is moved rather than deleted and is rejected by the post-move inode check; residue is
bounded and a detached credential copy is zero bytes. The three canonical slot names are fixed and
checkout-path-independent, so moving an installed checkout cannot strand unrecognized residue.
Older digest-suffixed slot names remain read-only during candidate validation and every rollback;
only successful post-core cleanup may normalize them into the fixed zero-byte, single-link slots.
An interrupted transaction whose journal already records the older names remains recoverable.
Every move remains on the candidate
filesystem, so an external-volume checkout never depends on a cross-filesystem rename into App
Support. Rollback prevalidates the original generated-runtime identity and every
checkpoint, cleans only an unbound transaction-owned staging file, and claims the candidate `.env`
through a rollback quarantine only when the hard-link identity proves activation created it. If a
launcher atomically rewrites `.env` with its exact checkpoint bytes and mode, rollback may retire
the now-detached transaction receipt only after an atomic no-replace quarantine claim and
revalidation of its recorded inode, size, and digest. The validated inode moves without replacement
into the same transaction-unique `0700` private directory beneath the candidate checkout, then uses
the same descriptor-bound move-only retirement path. Rollback therefore preserves a racing
replacement and also works when App Support is on a different filesystem. Different candidate state fails
closed and is preserved. A plan-only or independent concurrent
edit is preserved. A missing original runtime backup is a hard refusal, not a false rollback. Commit uses
a durable accepted-env receipt and rechecks the nested LibreChat revision at the publication and
commit boundaries. Commit-boundary source verification is a failure predicate: an unchanged
predecessor owner source proceeds to commit, while only a failed `verify-source` check may trigger
rollback. A successful verification must never be interpreted as evidence of concurrent drift.
A cleanup failure after `core_committed` records `ownerEnvCleanupState=pending`; alignment status
remains readable, rollback stays forbidden, and helper finalization refuses to delete the journal
until a later forward retry completes cleanup. Cleanup hygiene can therefore delay finalization but
cannot reverse a healthy committed runtime or silently discard its recovery receipts.
A post-acceptance owner edit is preserved and forces an additional alignment
restart before helper finalization when the candidate is running. That restart is bound to exact
pre-restart bytes and uses the current candidate owner file as canonical; finalization refuses
if the content changes before post-health acknowledgement, while a safe same-content launcher
rewrite may change inode without false drift. Deleted keys are not
reintroduced from the older staged source. The launcher may advance only
declared runtime-owned fields and must preserve
persisted auth/encryption, provider, Meili, Google, code-interpreter, Firecrawl, empty assignments,
and unknown owner values across the first and later helper starts.

The owner-environment transaction defends ordinary concurrency: launcher rewrites, editor atomic
saves, a second Viventium invocation, interruptions, crashes, and retries. An actively malicious
process already running as the same UID is outside this filesystem boundary because it can directly
rewrite or remove `.env`, the checkout, and App Support. macOS has no public inode-conditional
pathname-removal primitive; the enforceable product invariant is therefore that activation never
removes a directory entry that may contain owner-environment value.
Environment mutators must also be true no-ops when the requested assignment already exists exactly
or a requested removal is already absent, avoiding needless inode replacement and reducing
pre-commit race surface without treating inode stability as the semantic authorization boundary.

## Telegram Recovery Controller And Preference Continuity

Cross-checkout activation has two distinct identities:

- source provenance remains the selected predecessor/candidate checkout;
- installed Telegram execution is a verified content-addressed App Support code root and Python.

Before publication, activation stages predecessor and candidate components without changing the live
selection. After an accepted candidate publishes, detached macOS startup requires that installed
identity. On rollback, the current packaged compatibility launcher is retained with the staged
component and runs against predecessor source roots while forcing Telegram code, dependencies,
handoff helper, and preference state through App Support. This preserves compatibility even when
the predecessor checkout predates installed-component awareness.

An established repo-local `TelegramVivBot/user_configs` directory is a legacy personalization
source, not a runtime location. After the predecessor writer is quiesced, activation migrates it into
canonical App Support, keeps the legacy directory as a recovery copy, and records private
content-hash/backup evidence. Rollback intentionally retains this forward-compatible migration.
Explicit custom config roots remain authoritative. Startup must not persist newly introduced
defaults or overwrite a stored legacy system prompt; missing values stay an in-memory view until an
actual user preference change.

### July 25, 2026 Escaped Activation Recovery Learnings

- The activation journal persists the exact owner-private staged Telegram recovery selection.
  Restarted recovery never guesses an attempt-specific filename; legacy journals may use only a
  unique validated staging candidate.
- Detached compatibility recovery exports the canonical App Support base/state roots and runtime
  profile before invoking either launcher. A checkout-relative default state directory is forbidden.
- ANSI-colored progress text cannot turn the documented nonterminal
  `Remote access setup failed; local startup will continue` condition into a terminal startup
  failure.
- A router/public-edge conflict remains visible in status but does not block or roll back a healthy
  localhost runtime. This implements the remote-access requirement that local startup survives
  unavailable public mappings.
- GlassHive readiness probes the actual configured MCP transport plus runtime/UI health; deployed
  FastMCP builds are not required to invent a separate MCP `/health` route.
- Incompatible Meilisearch recovery is limited to derived default state, uses a no-follow
  owner-private archive, validates all process/container ownership before any signal, and aborts
  before archive on any ownership or stop failure.

## Update Check

`bin/viventium upgrade --check --json` reports update availability and blockers without pulling,
writing Git metadata, creating App Support state, compiling, installing helpers, or touching the
running stack. Remote observation uses `git ls-remote`; when the remote commit is not already in the
local object database, `commits_behind` is a lower-bound signal and `remote_history_complete` is
false rather than pretending an exact history count was available. The check requires the current
branch's explicit remote+merge configuration; it does not silently assume `origin`, and the mutating
pull uses that same configured pair.

The helper uses this for **Check for Updates...**:

- Up to date
- Update available
- Update blocked
- Offline or git error

Installing an update still uses the canonical `bin/viventium upgrade --restart` path.
The check also reports and blocks on helper fallback rebuild need using the same package-source hash,
binary SHA-256, executable, and universal-architecture contract as `install_macos_helper.sh`, so the
helper does not present missing, corrupted, single-architecture, or stale package state as aligned.

The machine-readable exit contract is:

- `0`: inspection completed and an update/repair can safely be attempted; this includes clean
  selected components that need refresh to their configured pins
- `2`: remote or Git inspection could not complete
- `3`: a policy/safety blocker exists, including a dirty selected component, invalid/unverifiable
  lock entry, dirty parent checkout, or stale helper artifact

The JSON keeps `component_lock_drift` for blocking component states and reports safe clean movement
under `component_refresh_required`. When canonical config exists, only components selected for that
installation block its upgrade; other managed checkouts remain release diagnostics. The helper must
require schema version 1 and typed readiness/update/blocker/count/component fields, then parse valid
JSON even when the process returns `2` or `3`, so a person sees the concrete blocker instead of a
generic command failure. Parent dirtiness includes untracked user work while declared managed
component roots are classified by the component inspector rather than double-counted as parent files.
A stray untracked parent file is therefore an intentional fail-closed upgrade refusal: the CLI must
tell the user to preserve/remove the file and retry, or use the explicitly local-only
`--skip-pull --allow-dirty` path. The synthetic regression must prove refusal occurs before App
Support creation or source/component mutation and that the untracked file remains unchanged.

The mutating upgrade path refuses a running stack without `--restart` before pull or continuity
mutation, runs the structured local-safety inspection before pull/stop/component mutation, captures
and gates a trustworthy pre-upgrade continuity baseline while services are still available, and
fails if the stack cannot stop. `--allow-dirty` is accepted only with `--skip-pull`. Automatic
recovery is journaled rollback, not an availability restart from partially changed disk state. The
transaction is registered and its recovery trap is armed before stop; after stop, the CLI verifies a
private checkpoint of source identities, config/runtime, product-owned runtime/bootstrap/data state,
legacy Mongo paths, and the active Docker Mongo named volume when applicable. Source activation,
component refresh, candidate compile/doctor, and health-checked restart occur while that checkpoint
remains active. Candidate config/runtime are activated only after validation. System prerequisites
are check-only during upgrade because system package installation cannot be rolled back; the user is
told to apply a missing prerequisite separately and retry. A post-upgrade continuity `error`,
`unknown`, malformed result, capture failure, compile/doctor failure, component drift, or failed
restart invokes rollback and restoration of the prior running/stopped state. Unknown local commits
or tracked edits make rollback fail closed instead of discarding work. Newly cloned managed
components are retained under the private transaction quarantine and removed from their formerly
absent managed path. Exact stopped file/volume restoration is verified, while semantic reversal of
arbitrary data migrations remains explicitly unproven. Helper refresh remains unlaunched until an
accepted post-audit and successful runtime restart, preventing helper login auto-start from racing
the gate. After component bootstrap, the CLI reruns structured component alignment; stdout wording
is never a safety gate.

## Safety Rules

- Do not add a second active-checkout pointer. Use the existing App Support `active-checkout.json`.
- Do not hide config changes in environment-only paths. Dev env config is written to that env's
  canonical `config.yaml`.
- Do not silently update nested repos or `components.lock.json`.
- Do not treat a dirty checkout as release-ready. Dirty local testing requires an explicit local-only
  acknowledgement.

## QA Requirements

Acceptance requires proving:

- dev env app-facing ports differ from the installed runtime
- singleton services are not duplicated by default
- update check is side-effect-free
- activate-current uses the existing runtime-checkout path
- helper update UX can report up-to-date, blocked, and update-available states

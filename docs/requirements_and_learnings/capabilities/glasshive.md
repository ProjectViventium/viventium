# xPerfect (GlassHive compatibility)

## Component and compatibility

The managed worker component is [xPerfect](https://github.com/xPerfectAI/xPerfect),
installed at `viventium_v0_4/xPerfect/`. The retained GlassHive checkout is not a managed
source or fallback. Existing `integrations.glasshive` config, `glasshive-harness` provider
IDs, environment variables, supported protocol routes, and `glasshive` state directories remain
compatible. Changing the source dependency does not move or recreate user state.

The former provider-owned `main_context_v1` claim (`main_context_owner=provider_legacy`) is not a
supported route in the current component. Viventium sends Core-owned V1 snapshots from its accepted
conversation history after upgrade; it keeps the configured `glasshive-harness` provider and model.
An old caller that still asserts provider-owned V1 receives an explicit request error. Ordinary
standalone conversations without a V1 claim remain supported, but do not gain cross-thread Main
memory from that path. Preserve old provider context rows in the state checkpoint for inspection and
rollback; do not treat their bounded excerpts as a complete Core history or import them silently.

## User promise

GlassHive may serve as an authorized Main provider or as durable worker execution. Both paths must
produce useful results, preserve the user's full task, and expose honest fallback and recovery.

## Provider and workspace

### Provider outcome

- **GHM-001 / GHM-004:** GlassHive can be selected as the real Main or cortex provider; conversation
  and mission paths each meet the outcome metric and expose fallback truth.

### Provider contract

- **GHM-002 / GHM-003:** One selected authoring intelligence receives the authorized identity,
  context, workspace, model, tools, memory, and Feelings for the turn and reuses canonical per-user
  LIFE without duplicating context or runs.

Provider defaults are `codex-cli:gpt-6.1-sol`, `claude-code:claude-opus-5-5`, and
`grok-build:grok-4.7`, each at high effort. `grok-build:grok-4.7-build-fast` is also selectable.
Other supported models and efforts remain available. If the native catalog does not offer
Grok 4.7 Fast but offers Grok 4.7, a Fast request uses Grok 4.7 and reports that actual model.
Grok uses its native ACP system rules for
server-owned agent instructions and the existing private worker sign-in boundary.

### Optional Direct API execution

The same xPerfect provider catalog can select `direct-openai:gpt-6.1-sol`,
`direct-anthropic:claude-opus-5-5`, or `direct-xai:grok-4.7`. Each recommends High;
native defaults and supported alternatives remain unchanged. Direct is an executor choice for the
existing Queen or ordinary workers, not another orchestrator. It uses the official single-agent
SDK and the existing xPerfect host supervisor, account binding, MCP projections, history, work
controls and callbacks. API credentials and API billing are separate from CLI subscriptions.
An explicitly selected account must supply its own authorized key; an ambient key cannot replace it.

An operator can configure an OpenAI-compatible HTTPS Responses deployment, including Azure v1,
through `runtime.extra_env.WPR_OPENAI_BASE_URL` and a separate
`WPR_OPENAI_API_KEY` Keychain secret reference. The model ID must match the deployment name.
This changes only deployment-managed Direct OpenAI execution. It must not replace the global
OpenAI credential or send a selected personal account's credential to a custom deployment.
The endpoint participates in the scoped history/cache identity. Default public OpenAI execution
is unchanged when these settings are absent. Do not expose endpoint selection to conversation text.
Keep this dedicated pair in the private provider environment. It is not part of the native-worker
provider allowlist and must stay out of gateway and general runtime environment files. Core's
native-worker allowlist must match xPerfect's projection contract.

Direct exposes only real configured tools. Native computer or shell work uses authorized MCP tools
or the existing worker handoff. Shared context references do not imply free provider context or a
transferable prompt cache. Retain protocol, tool, reasoning and message identifiers across turns.
Internal commentary and skip-voice parts remain outside speech. Keep worker safety instructions
and each role's complete, correctly ordered authority.

Respect the admitted context owner and protocol. A repeated canonical Core snapshot is not another
user turn to append indefinitely to SDK history. Delta input still needs its accepted prior state.
Any history reduction must preserve actual user turns, files, native tool-call/result pairs and
reasoning identifiers; a role label or output schema alone does not prove a stateless context.
The Direct request projection keeps the first trusted Core archive copy and omits later exact
duplicates only when admitted origin and content hashes match. It preserves the earlier request
prefix, all unique content and the raw SDK journal. Unmarked legacy inputs remain unchanged. This
reduces provider input; it does not compact the journal or prove a latency or reliability gain.

Direct uses the shared native conversation-parts collector for streamed replies, terminal text and
mixed speech dispositions. Final output must pass the owning schema and conversation controls;
plain provider sampling does not make arbitrary text eligible for speech. Completed native tool
rounds are checkpointed before the next provider request, preserving actual tool identifiers if
generation stops. Do not fabricate tool results or automatically replay uncertain effects.

Account selection and binding must require API-key authentication for a Direct executor while
preserving native subscription choices. The existing host supervisor owns the execution deadline;
an independent short HTTP read timeout must not cut off an otherwise authorized longer run.

Core's active-work capsule can carry an exact compiler-authored DATA range through the existing
Main-context metadata. For Direct, the current full roster stays visible. Only older consecutive
identical bound rosters can be omitted from outgoing history; changed, unmarked or other-epoch
inputs break coverage. Unique goals, files, tool returns and the raw journal remain intact. This
complements exact static-archive projection and does not rewrite legacy history or native CLI
sessions. Content-free block/byte counts use the existing Direct stage event.

Stateful Direct OpenAI/xAI calls also send the official prompt-cache routing key, hashed with a
versioned domain from the complete existing history scope. No key is sent for Anthropic, stateless
or private machine-state calls. Server response storage remains disabled and retention is unchanged.
A key is a routing hint, not a promised cache hit or speedup; fresh authorization is still required.

Direct execution is host-only and starts cold by default. The existing worker startup settings can
optionally keep 0–8 import-only SDK processes ready per worker, with 10–3600-second expiry. This
reuses xPerfect's NativeWarmPool and aggregate 16-global/8-owner limits across Grok and Direct.
Idle processes carry no account key, grant, history, tools or model request; each single-use admitted
run receives its fresh authorized inputs. A ready existing Queen/worker can skip SDK imports; a new
worker is cold unless it was already configured and ready. Missing readiness keeps the normal cold
path. Fresh authentication, tools, history and client construction remain measured work, not provider
KV-cache reuse. Default count is zero; an isolated import-only observation used about 113–133 MiB
per idle process, so eight can use about 1 GiB before active work. This estimate varies by installed
SDK/provider modules and platform. Source tests and isolated import checks are not end-to-end voice acceptance.
Configured options must be sent faithfully or report an unsupported configuration; do not silently
drop options to make the request pass.
Grok 4.7 supports Low, Medium, High and XHigh reasoning, not disabled reasoning.

Stop ends the local executor and its ability to make further tool calls. It does not prove that the
provider stopped cloud inference or billing. Preserve accepted durable work, uncertain action
receipts and late-output fences; do not automatically replay uncertain effects. No separate remote
execution manager or indefinite GPU-capacity lock is required for that distinction.

Confirmed native Stop, Pause, Steer replacement and termination retain the exact run, attempt,
stop reason, transcript reference and native media. Their acknowledgment must not inventory a
shared working folder, render deliverables, or infer a provider failure from an already confirmed
stop. These completion audits cannot prove which stopped run created a file in a shared folder.
Mark those audits not applicable for that stopped generation; keep existing files and their
catalog. Large transcript previews may link to the retained source instead of scanning the full
transcript for an inline excerpt. Normal successful and failed completion audits remain unchanged.
Measure native stop proof separately from evidence preparation and the Queen's next reply.

Source implementation is separate from installed-path acceptance. Provider availability, actual
Queen/worker handoff, history, streaming, cancellation and affected Voice/Text/Telegram paths need
candidate-bound evidence before claiming full parity. Shared API-key setup retains native CLI
credential-artifact compatibility; an installed but failing native setup command can still block
that shared connection path. Direct Docker placement and universal API-only setup are not delivered.

Performance reports must separate a tiny direct model request, prepared context, the current
typed reply/tool contract, and first received speech. Count a rejected API request as a failure,
not a fast response. Record the actual supported thinking setting; Low does not mean Off.
Report first context processing separately from prefix reuse. A fast local answer that cannot
preserve the typed reply, silence and exact work controls is not a working Queen.
Use plain stage names: "record this reply once, then start it" describes immediate execution
bookkeeping, not a calendar timer. A future host replacement removes its adapter code, not the
need to preserve the account, relevant context, allowed access, Stop and durable work receipts.
Do not subtract a whole mixed stage as a future saving unless its removable part was measured.

### Backlog

OpenCode model and effort parity is deferred. Keep its current routes unchanged until a separate
request resumes that work.

### Non-goals

- **GHM-005:** Implement the concrete provider path without speculative platform expansion.

### Experimental local inference

The [local-model research owner](../../research_and_future_plans/05_Local_Models_and_Native_Harnesses.md)
records native xPerfect Main/worker feasibility and its limits. This is not an installed provider
promise or a change to the defaults above. The existing host-worker cases `GHHOST-027`–`029` and
their dated report own qualification; raw model speed is not provider, worker or offline acceptance.

### Identity and connections

- **GHU-001:** Users get standards-based sign-in under the deployment's configured account-creation
  policy.
- **GHU-003 / GHU-004:** Users can connect, verify, renew, reconnect, or remove a personal supported
  provider without changing another user or the deployment default. Contention, quota, and expiry
  each provide one truthful recovery action.

### Tenant safety

- **GHU-002:** Persistent workspace and state are isolated by enforced owner and tenant boundaries.

### Workspace experience

- **GHU-006 / GHU-007:** Workspaces have clear editable names and are easy to find, favorite, link,
  reopen, and reuse at one canonical URL without needless reauthorization.
- **GHU-013:** Home opens the canonical dashboard. Opening a result shows the exact scoped artifact
  without restarting compute; Watch and Continue remain explicit actions.
- **GHU-009:** The primary workspace UI is sparse, accessible, responsive, and truthful without raw
  terminal output.

### Workspace control

- **GHU-014:** Users can view, Steer, and control parallel workers from one bounded workspace
  surface; inactive cards remain truthful without unbounded streams.

### External client setup

- **GHU-015:** Native clients offer an accessible automatic setup path plus advanced manual setup,
  with end-to-end reconnect and recovery.

## Mission boundary

### Mission envelope

- **PW-054:** The mission receives the complete task, constraints, inputs, exclusions, output shape,
  and success condition without semantic loss.
- **PW-055 / PW-056:** Context and capabilities are limited to what the mission needs and exclude
  unrelated private data, credentials, host secrets, and sibling context.
- **PW-057:** Descendants may inherit but never expand authority; a missing broker never permits a
  native bypass.

Ordinary mission launches retain their reviewed connected-service permissions but defer server
discovery. Their initial MCP catalog exposes the existing discovery helpers and resolved host
tools; the worker chooses a service with `capability_describe` and invokes it through
`capability_invoke`. Unrelated services must not delay the first model request. Successful discovery
reuses the existing grant-and-server cache for describe and invoke, after current user, policy and stored-credential
checks. A selected service still uses normal connection/authentication and can report unavailable.
This saves eager startup and schema tokens; a genuinely needed service can add a discovery tool round.

The explicit eager/deferred partition belongs to the durable authorization fingerprint, signed
run grant, worker projection and visible instruction context. Existing authorizations without this
partition keep their eager behavior on replay and Resume. Standalone operator and scheduled
defaults and the conversation's explicitly declared tools remain unchanged.

### Native harness boundary

- **GHU-005:** Use native harness capabilities inside the isolated workspace. The host does not copy
  credentials or reimplement connector behavior.

### Interaction

- **GHU-008:** A short request starts the smallest goal-relevant action and reports work without
  exposing plumbing.

### Typed capabilities

- **PW-059:** Routes, models, effort, fallback, surfaces, and capabilities come from current typed
  metadata, not prose or tool-name inference.

## Inputs, results, and fallback

### Artifact provenance

- **PW-060 / PW-061:** Inputs preserve exact identity, bytes, order, grouping, captions, and owner
  scope. Missing, unreadable, or unauthorized bytes fail truthfully; captions never replace files.

### Result delivery

- **PW-062 / PW-063 / PW-064:** One authoritative envelope returns text, sources, structured output,
  files, media, and artifacts exactly once. Results remain available at the origin and Active Work;
  unsupported rendering gets a stable handoff, and absent, duplicate, dead, or foreign artifacts
  are never claimed. A media-link caption for a canonical file in the same callback does not
  create another attachment when its authorized download URL, hash, size and MIME type match.
  Preserve distinct grants, callback origins and all intentional canonical filenames.

### Fallback and authority

- **PW-065 / PW-066:** Fallback preserves mission, workspace, controls, inputs, capabilities, output
  ability, and authority ceiling or reports blocked. Admission mints authority; revalidation cannot
  expand it and expired or revoked authority pauses for input.
- **PW-067:** Long-running authority is time-bounded by
  `config.schema.yaml` → `integrations.glasshive.orchestration.authorization_horizon_seconds`;
  `scripts/viventium/config_compiler.py` → `resolve_glasshive_orchestration_settings` validates and
  compiles it to `VIVENTIUM_GLASSHIVE_AUTHORIZATION_HORIZON_SECONDS`. Resuming after expiry needs
  user authorization. The schema range is 60–86,400 seconds; deployments choose the value.

### Lifecycle truth

- **PW-113:** Project lifecycle comes only from provider events. Unsupported child visibility stays
  absent while observed root output remains available.

## Owners and QA

- Provider and mission runtime: `viventium_v0_4/xPerfect/`
- Host brokerage and user presentation: `viventium_v0_4/LibreChat/`
- Mission lifecycle architecture: [Parallel Work runtime](../../architecture/parallel-work-runtime.md)
- QA: `qa/glasshive-core-provider/`, `qa/glasshive-mcp-capability-broker/`,
  `qa/glasshive-user-control-plane/`, `qa/glasshive_host_workers/`, and related GlassHive folders

Real acceptance uses an owner-scoped installed account, a natural request, provider and broker
evidence, visible progress, exact artifact delivery, reconnect, restart, and fallback or blocker
wording. A reachable host endpoint alone does not pass.

## Detailed contracts

- [GlassHive Workstation Sandbox Runtime](../48_GlassHive_Workstation_Sandbox_Runtime.md)
- [GlassHive Workflows Self Healing and Feature Requests](../51_GlassHive_Workflows_Self_Healing_and_Feature_Requests.md)
- [GlassHive User Control Plane and Persistent Workspaces](../57_GlassHive_User_Control_Plane_and_Persistent_Workspaces.md)

Declared provider model IDs must remain available when a fetched model catalog is cached. The
shared catalog projection serves Main, Voice, fallback and model selectors, so a displayed
capability label cannot hide an executable-model rejection. API connection readiness confirms
configuration only; model access is checked on the actual request. Generic parameter controls
follow the public endpoint drop list. Direct API controls do not claim native shell sandboxing
or native tools. These contracts apply to all shared Agent model parameter surfaces.

### Capability instructions and failed consultations

A local orchestration facade is not the complete MCP server behind its historical tool ID.
Project instructions from the exact declared callable surface. Do not load full source-server
instructions merely because a facade ID retains an MCP suffix. Actual MCP tools still receive
their server instructions, including when the same agent also has local facades.

An explicitly rejected model request in a hidden specialist consultation returns through the
existing scoped error handoff to its caller. Preserve the original user turn and the caller's
own capabilities. The caller decides what remains possible. This is not an automatic retry,
provider change, or replay of accepted actions. Tool failures, cancellation, source-integrity
failures and fatal errors retain their distinct handling.

These are capability and error-provenance contracts. They do not prescribe which requests the
model should delegate or consult, and they do not prove full provider or channel parity.

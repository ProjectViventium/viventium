# Installed Agent Builder GlassHive Fallback QA — 2026-08-04

## Outcome

`GCP-019` and `TELEGRAM-UC-010` are **PASS** for the installed local-prod runtime. The generic
LibreChat Agent Builder fallback is GlassHive / Claude Opus 5 with high effort. The live Agent
database, installed source, compiler-owned generated config, and future bootstrap template agree.
GlassHive's separate provider-internal fallback is independently configurable and remains disabled
by default on every managed Agent.

The reported `Connection error. Please retry.` was not a failed model switch. The installed
LibreChat API was unavailable because helper recovery could not open a legacy owner-owned
`helper-start.log` at mode `0644`. Once submission was repaired, repeated supervisor launches could
also overlap the several-minute search-index/client warm-up and kill the preceding launch. The
installed helper now safely tightens that legacy log to `0600` and keeps one controller-level launch
in flight across the entire health-wait operation. A CLI/helper race could still occur while a manual
restart replaced the process-group receipt; an owner/PID/repository-bound startup claim now bridges
that window. Cold helper recovery and a later manual restart under helper supervision each completed
with one runtime owner, and fresh real Telegram turns succeeded after both.

The real browser rerun also exposed that the fallback panel was not receiving the provider capability
registry. The backend tuple was correct, but readiness, the friendly Opus 5 label, and route-scoped
effort were not fully auditable in the current UI. The primary and fallback panels now share the same
capability metadata, and the installed browser visibly saved and reloaded Opus 5 at High.

No unrelated user-managed Agent fields were overwritten. The live sync updated only
`fallback_llm_provider`, `fallback_llm_model`, and `fallback_llm_model_parameters`; a subsequent
source-owned handoff restoration preserved 18 live user fields.

## User-path evidence actually run

### Agent Builder

- Opened the installed runtime in a real browser with a temporary synthetic local session.
- Created a synthetic non-admin Agent through the supported API, opened its visible Model and
  Fallback Model panels, selected Provider `GlassHive`, Model `Claude / Opus 5`, and effort `high`,
  then used the visible Save button.
- Reloaded the full page, reopened the Agent and fallback panel, and observed `GlassHive`,
  `Claude / Opus 5`, `high`, and `Authenticated and ready` again.
- In the same installed UI, observed `Provider-internal fallback model` as disabled on a newly
  configured GlassHive Agent, selected `Claude / Opus 5`, observed the recommended effort become
  `high`, saved, reloaded, and observed both values persist.
- Cleared the provider-internal fallback, saved, reloaded, and observed it remain disabled. The
  separate Agent fallback still showed `GlassHive / Claude / Opus 5 / high`, and the
  provider-internal control was not duplicated inside that Agent-fallback panel.
- Mongo independently stored `glasshive-harness / claude-code:opus / high`. The same headed browser
  run completed native GlassHive chat, second-turn, redaction, cancellation, activity, and refresh
  checks with zero console, endpoint-UI, or critical HTTP errors.
- The broad harness also reported two unrelated existing failures: its Feelings frame count was zero
  and its Phase-B main-session completion delta was one rather than two. Those do not contradict the
  fallback/UI checks, but the broad harness result remains honestly non-green until their owning
  features are reconciled.
- Removed both synthetic Agents, their conversation/provider state, and the temporary browser session
  after QA. Private screenshots remain outside the public repository.

### Telegram quota recovery

- Sent a synthetic marker prompt through the real Telegram Desktop conversation with the installed
  Viventium bot.
- A one-shot local fault injected structured `provider_quota_exhausted` before primary authoring.
- Telegram visibly received exactly `TG_QUOTA_FALLBACK_OPUS_HIGH_20260804_1002` in the original turn, plus the normal audio
  delivery; no primary rate-limit bubble was exposed.
- The persisted LibreChat assistant message matched that text and was neither errored nor unfinished.
- Runtime logs recorded the retry from GlassHive/Codex to GlassHive/Claude Opus.
- GlassHive persisted one completed fallback request with a distinct `main-fallback:` idempotency
  key. Its worker profile was `claude-code`, model `opus`.
- The Claude audit recorded `--model opus`, `--effort high`, exit code zero.
- The one-shot fault hook and sentinel were removed, and runtime health was rechecked afterward.

### Telegram provider-unavailable recovery

- Sent a second synthetic marker through Telegram Desktop while a one-shot structured
  `provider_temporarily_unavailable` result replaced the primary pre-authoring result.
- Telegram visibly received the exact requested marker in the original turn with no generic
  connection bubble; the persisted assistant message was neither errored nor unfinished.
- GlassHive recorded one distinct completed fallback request. The replacement worker was
  `claude-code / opus`, and its action audit recorded `--model opus`, `--effort high`, and exit zero.
- The one-shot hook and sentinel were removed before the final clean restart.

### Telegram raw connection-refusal recovery

- Added a temporary installed-runtime-only one-shot sentinel immediately before the primary
  provider stream and raised a real Node-style `ECONNREFUSED` error with no structured provider
  classification supplied by the fault.
- Sent `TG_RAW_CONNECTION_FALLBACK_OPUS_HIGH_20260804_1246` through native Telegram Desktop.
  Telegram visibly received the exact reply and a `Voice.mp3` attachment; no `Connection error`
  bubble appeared.
- Mongo stored exactly one assistant reply for the turn with `error=false` and
  `unfinished=false`.
- GlassHive completed the fallback run through the `claude-code` runtime. Its action
  audit recorded model `opus`, `--effort high`, and exit code zero. Telegram independently logged
  the audio delivery as sent.
- Removed the temporary sentinel and source hook, let the installed backend reload the clean
  source, then sent `TG_HAPPY_CLEAN_PRIMARY_20260804_1250`. Native Telegram again showed the exact
  text and `Voice.mp3`; Mongo was clean and GlassHive completed the normal
  `codex-cli / gpt-5.6-sol / medium` route.

### Cold recovery and final clean Telegram turn

- Stopped the installed local-prod stack and observed the installed helper recover it.
- The helper submitted one recovery at `14:25:46Z`, reported the stack healthy at `14:28:41Z`, and
  submitted no overlapping recovery while search indexing and the web build were still warming.
- LibreChat API `3180`, web `3190`, playground `3300`, GlassHive API `8766`, and GlassHive MCP
  `8767` were concurrently listening; API/web/playground/GlassHive health returned success and the
  MCP root required authentication as expected.
- Sent `TG_E2E_RECOVERY_20260804_1031` through Telegram Desktop after recovery. The exact text and
  audio were visible in Telegram. Mongo stored the exact assistant text with `error=false` and
  `unfinished=false`.
- GlassHive persisted the final clean turn as a completed `codex-cli / gpt-5.6-sol` run with exit
  zero, proving the temporary degraded-path hooks were absent and the normal primary route still
  worked after repair.
- Repeated restart acceptance through the public CLI while the helper remained active. The startup
  claim was present across the observed API outage and absent after handoff; API/web/playground/
  GlassHive returned HTTP 200, the helper launched zero competing starts, and exactly one runtime
  process group remained.
- Repeated the opposite race direction from a stopped runtime. The helper-owned restart first held
  the ordinary CLI lock during preparation, then published the owner/PID/repository-bound startup
  claim before releasing that lock. A concurrent manual `start --restart` returned
  `Viventium is already starting.` with exit zero. The claim remained through search-index and web
  warm-up, then cleared only after API, web, playground, and GlassHive were all healthy.
- Sent `TG_STARTUP_CLAIM_E2E_20260804_1117` through native Telegram Desktop after that exact restart.
  The exact reply and audio were visible; Mongo stored `error=false`, `unfinished=false`, and GlassHive
  recorded a completed exact-output Codex run.

This run exposed and fixed a normalized-provider bug: live GlassHive Agents use internal provider
`openAI` with endpoint `glasshive-harness`. Capability and attempt identity must therefore prefer
the endpoint. The regression now exercises that normalized live shape and proves the fallback keeps
its distinct attempt key.

## Configuration and delivery evidence

- All 13 source-owned Main/background/handoff Agents carry exactly
  `glasshive-harness / claude-code:opus / high` in the public bootstrap template.
- The private current-user source and live database contain the same 13 fallback configurations.
- The live database has zero managed Agents with the provider-internal fallback enabled. The browser
  QA used a disposable synthetic Agent and removed it afterward; Mongo confirmed zero synthetic QA
  Agents remained.
- Generated installed config reports GlassHive `automatic_fallback_target: true` and Opus
  recommended effort `high`; the live `/api/endpoints` response agrees.
- The restarted installed GlassHive `/v1/models` endpoint returned HTTP 200 with only
  `codex-cli:gpt-5.6-sol` (recommended `medium`) and `claude-code:opus` (recommended `high`), both
  advertising both Agent-fallback-target and serial-fallback capability. Installed API, web,
  playground, and GlassHive health endpoints all returned HTTP 200 after browser QA and the final
  restart.
- Final installed status showed LibreChat API/web, modern playground, GlassHive, both Telegram
  services, and the macOS status-bar helper running.
- The helper-safe installed Scheduling Cortex component's copied source artifact was aligned
  surgically to the same capability, effort, and direct Opus 5 route without replacing its other
  runtime files.
- Active installed config, generated runtime output, and Viventium-owned source-of-truth/template
  surfaces contain no configured/default Sonnet 4.5 or Opus 4.8 route. Upstream provider
  compatibility code and regression fixtures can still recognize historical identifiers, but no
  Viventium Agent, compiler default, generated config, or live Agent selects them.

## Automated evidence

- Public backend fallback/client/cortex selection: 224/224 passed.
- Installed backend fallback/client/cortex selection: 227/227 passed.
- Public fallback/runtime suites: 192/192 passed.
- Installed fallback/sync suites: 212/212 passed.
- Installed Agent Builder helper suites: 31/31 passed.
- Installed helper suite after the recovery and startup-claim repairs: 43/43 passed.
- Public helper delivery suite after porting the legacy-log repair: 18/18 passed; the Swift release
  build succeeded, the shipped universal artifact contains both `arm64` and `x86_64`, and its recorded
  binary/source hashes match.
- Stable runtime/detached supervision selection: 72 passed, 1 skipped.
- Installed LibreChat fallback/provider selection: 39/39 passed.
- Installed Telegram bridge suite: 129/129 passed.
- Installed capability-backed fallback panel: 2/2 focused Jest tests passed.
- Installed shared provider-controls/fallback panels: 18/18 focused Jest tests passed.
- Installed GlassHive provider suite: 85/85 passed, including structured quota switching to Opus 5
  High, no switching on unstructured text, no switching after native authoring/tool activity, and
  exactly one fallback winner under concurrent observers.
- Public bootstrap GlassHive provider suite: 54/54 passed.
- Installed compiler suite: 188/188 passed after adding exact retired-model override rejection.
- Public/bootstrap compiler suite: 151/151 passed.
- Installed pricing/release-contract/Skyvern route selection: 171/171 passed after replacing the
  stale Opus 4.8 pricing case with Opus 5.
- Public Agent-level fallback/payload coverage: 2/2 focused Jest tests passed using the installed
  checkout's matching `jest-environment-jsdom`. The public provider-internal controls are inline in
  its `ModelPanel` rather than the installed checkout's refactored shared component. The public
  checkout still has a pre-existing Jest runtime/mocker version mismatch in its own dependency tree.
- A review-only Opus 5 pass found that the public GlassHive registry still recommended `max` and
  disagreed with the compiler about Agent-fallback eligibility. Both public and installed registries
  now recommend Opus `high` and publish `automatic_fallback_target: true`; the provider suites and
  restarted live registry passed afterward.
- The follow-up review withdrew its earlier bootstrap NO-GO after directly verifying the public
  inline Agent Builder behavior and corrected registries. Final scoped verdict: **GO** for both the
  installed runtime repair and the public source/bootstrap working tree.
- Per the user's instruction, no commits or pin updates were made. Publishing later still requires
  the normal nested-repo commit → `components.lock.json` pin update → parent commit sequence; that is
  release work, not missing source behavior in this uncommitted working tree.
- Cross-process startup-claim regression and surrounding detached-launch selection: public 5/5 and
  installed 4/4 passed before the full affected suites.
- Public startup/helper selection after the bidirectional race fix: 76/76 passed.
- Installed helper/upgrade selection: 152 passed; 13 upgrade-transaction cases stopped at the
  existing 11-GiB free-space safety gate before reaching their synthetic transaction scenario.
- Broad compiler/governance selection: 290 passed before two stale direct-Anthropic fallback
  assertions were corrected; their focused rerun passed. One unrelated pre-existing productivity
  prompt assertion remains outside this change.
- The public checkout's frontend Jest dependency tree could not start these two suites because its
  Jest runtime/mocker versions disagree. The identical installed suites passed, and the real browser
  path passed before and after reload.
- Repository-wide frontend typecheck is also non-green in hundreds of unrelated baseline files on
  both worktrees; neither changed fallback component appears in the reported TypeScript errors.
  Focused ESLint has zero errors (four existing nested-ternary warnings in `AgentPanel`).

## Acceptance result

- Happy path: **PASS** — cold helper recovery, normal GlassHive/Codex Telegram text, persisted message,
  visible audio, and primary provider audit agree.
- Quota/rate pre-authoring failure: **PASS** — the same Telegram turn used GlassHive/Claude Opus 5
  at high effort exactly once.
- Provider-unavailable pre-authoring failure: **PASS** — the same Telegram turn recovered through the
  configured fallback without a generic connection error.
- Raw provider connection refusal: **PASS** — a real unstructured `ECONNREFUSED` entered the same
  Agent Builder fallback, delivered Opus 5/high text and audio, and left no error message.
- Provider-internal fallback configuration: **PASS** — disabled default, Opus 5/high save and reload,
  clear and reload, and separation from Agent-level fallback were all proven in the installed UI and
  persisted database.
- Runtime/API outage recovery: **PASS** — the repaired helper completed one recovery without an
  overlapping restart and Telegram worked immediately afterward.
- Cancellation: **PASS** — real browser Stop persisted one unfinished harness-activity message,
  authored no terminal answer, and remained visibly cancelled after refresh.
- Broad unrelated Feelings/Phase-B assertions: **FAIL outside this fallback repair** — captured above;
  they are not presented as green or used as fallback evidence.
- No destructive user data or live Agent fields outside `fallback_llm_*` were changed.
<!-- qa-evidence-exempt: Historical or specialized supporting artifact retained without retroactively inventing missing evidence; current release acceptance requires a fresh full-view report. -->

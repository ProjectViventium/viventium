# GlassHive Core Provider Acceptance — 2026-07-30

## Summary

- Result: `PASS` for the GlassHive core-provider product and installation contract. The installed
  Main is GlassHive / Codex and survived cold restarts. Current Codex conversation availability is
  `BLOCKED` by the signed-in provider account's external usage quota; the endpoint now reports that
  condition precisely as OpenAI-compatible HTTP `429` without fallback, retry, or duplicate authorship.
- Scope: universal GlassHive conversation endpoint, normal Agent Provider/Model integration, canonical
  LIFE, current Main migration, cortex/Phase B/Feelings boundaries, Telegram/LiveKit parity, degraded
  recovery, clean install, and release artifacts.
- Environment: installed local runtime plus a fresh supported clone/install using isolated App
  Support state and synthetic public-safe QA data.
- Tester: Codex, Playwright, Computer Use, and a review-only ClaudeViv Opus 5/max pass.

The implemented boundary is deliberately small: GlassHive owns one authenticated harness execution
core and exposes both OpenAI Chat Completions and Responses wire surfaces. LibreChat consumes Chat
Completions as a normal custom provider; other clients may use either surface. MCP remains a separate
tool/context broker and does not wrap conversation authorship.

## Scope Run

| Case | Status | Actual evidence |
| --- | --- | --- |
| GCP-001–002 | PASS | Real Agent Builder showed GlassHive and both exact models. Ordinary and cortex Agents round-tripped provider, model, LIFE/custom workspace, access, effort, versions, reload, API, and Mongo without coercion. |
| GCP-003 | PASS | Absent/partial automated bootstrap and a fresh supported install were additive and idempotent. The live canonical LIFE kept personalized content and gained no runtime scaffolding. |
| GCP-004–006 | PASS | Post-fix installed-browser QA completed natural Codex/Claude conversation, file/tool work, visible activity, multi-turn correction, refresh persistence, one reply, and one native session. A real Main turn after cold restart returned the exact requested final answer. Missing terminal events fail loudly. |
| GCP-007 | PASS | Post-fix installed-browser Stop produced one cancelled run and no late answer. Refresh/reconnect retained completed activity and conversation state; cancellation cannot resurrect during synchronization. |
| GCP-008–009 | PASS | Phase A remained direct, cortex used its own provider, Phase B reused the main GlassHive session, and Feelings appeared exactly once at the main authoring boundary and never in specialist/activity/LIFE state. |
| GCP-010–011 | PASS | Computer Use exercised Telegram text, voice note, circular video note, and a real LiveKit call. Telegram produced one harness-authored response per input; LiveKit remained Voice LLM. |
| GCP-012–013 | PASS | Invalid model/effort/path, stopped/missing/authless/busy/crashed harness, missing tool auth, access modes, file work, and native tools failed or succeeded precisely with no OpenAI substitution. |
| GCP-014 | PASS | An 808.54-second mission ran beside an interactive reserved lane. Health remained responsive; capacity retry, interruption, process restart, and recovery completed without duplicate authorship. |
| GCP-015 | PASS | Split-stream secrets and private paths were absent from installed UI, Mongo persistence, GlassHive output, and the post-fix log scan. Redaction occurs before stream and persistence boundaries. |
| GCP-016 | PASS | The pre-quota three-provider matrix passed all seven conversational/native cases for each provider. The stronger repeated rerun passed direct and GlassHive Claude `15/15`; GlassHive Codex was correctly marked externally blocked after one `429`, not mis-scored or substituted. |
| GCP-017 | PASS | The latest pushed parent branch clean-installed from an empty clone with isolated state, fetched both exact nested refs, bootstrapped LIFE, and generated Main/endpoint/capability config. The installed runtime uses the same checkout and retained Main after cold restarts. |
| GCP-018–019 | PASS | Stock OpenAI SDK clients passed Chat Completions and Responses non-stream, stream, message/instruction input, and same-owner continuity. Cross-owner continuity and credential cross-use were rejected. |
| GCP-020 | PASS | Missing native terminal events fail loudly instead of promoting a working preamble. Post-fix installed Main and SDK runs used only the terminal Codex agent message or Claude result as the authored answer. |
| GCP-021 | PASS | Busy/retry/restart cleared active failure state while preserving retry audit fields. |
| GCP-022 | PASS | A real exhausted Codex CLI quota produced HTTP `429`, `rate_limit_error`, and `rate_limit_exceeded`; DB state recorded one failed request/run, `provider_rate_limited`, zero retries, and no fallback. Chat Completions and Responses non-stream/stream regressions pass. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: GlassHive as a portable AI conversation endpoint and normal Viventium Agent provider.
- Requirement: any eligible main or cortex Agent can use a harness directly in the selected folder,
  with no wrapper LLM, silent provider substitution, recursion, duplicate authoring, or runtime state
  written into LIFE.
- Use cases: Provider/Model configuration, multi-turn correction, files/tools, activity, stop/refresh/
  restart, cortex/Phase B/Feelings, Telegram, LiveKit, load/degraded recovery, and clean install.
- QA cases: `GCP-001` through `GCP-022`.
- Expected result: one native harness-authored answer plus normalized activity, exact persistence,
  capability-filtered routing, and honest failure/recovery.
- Remaining product gap: none in the accepted feature scope. Operational availability of the
  canonical Codex model remains externally blocked until the signed-in account's quota resets or an
  operator authenticates an account with available quota; GlassHive Claude remains independently healthy.

## Full-View Evidence Checklist

| Evidence surface | Result |
| --- | --- |
| Requirements/docs | Core-provider, LIFE/installer, Feelings, background-agent, systems-map, and runtime QA truth were inspected and updated. |
| Owning code | Compiler -> generated endpoint/capabilities -> Agent schema/Builder -> LibreChat graph -> GlassHive provider/session/profile/store -> UI/Telegram/voice was traced. |
| Nested repos | LibreChat and GlassHive changes have independent commits; parent pins their exact refs. |
| Generated/shipped state | LibreChat YAML/env, Agent source, exact component refs, package/client build, provider lock, and installed runtime were inspected independently. |
| Logs/DB/state | Browser SSE, Mongo Agent/message/content parts, GlassHive request/session/run/activity, private manifests, process logs, and provider health correlated. |
| Real user paths | Playwright used the installed Agent Builder/chat. Computer Use independently exercised Main web, Telegram media, and LiveKit. |
| Install path | A fresh remote branch clone ran the supported installer with isolated App Support; preflight, compiler, component bootstrap, LIFE, and doctor passed. |
| Source safety | Legacy LIFE before/after manifests were identical; private raw evidence and credentials remained outside public repos. |

## User-Grade Evidence

- Surface exercised: installed LibreChat Agent Builder/chat, Telegram Desktop, LiveKit playground,
  direct OpenAI SDK, supported installer, and runtime CLI.
- Real user path: configure ordinary/cortex Agents, save/reload/version, chat and correct, read/edit
  a synthetic LIFE file, use a tool, inspect activity, stop, refresh, restart, trigger cortex/Phase B,
  send Telegram text/voice/video, and place a LiveKit call.
- Visible outcome: friendly GlassHive/model labels, LIFE/full/effort/readiness controls, one natural
  answer, honest activity/cancellation/cards, and no duplicate or late second voice.
- Expanded/detail state: provider options, activity steps, cortex card, cancellation, and versions
  were inspected before and after refresh.
- Persistence/reload result: Agent options, conversation, activity, session, cancellation, and
  Phase B state persisted; a restart recovered queued work.
- Local/external prerequisite state: both harnesses are authenticated. Claude is healthy; Codex is
  presently quota-limited by its provider. Missing-binary/auth/tool, stopped-service, and exhausted-
  quota cases produced explicit degraded states.
- Evidence retrieval classification: GlassHive provider and harness routes were healthy; deliberate
  missing-auth/config cases were classified as unavailable rather than empty success.
- Fallback path: GlassHive was never an automatic fallback target and was never silently remapped
  to OpenAI. Direct auxiliary classifiers/titles/memory/voice retained their configured boundaries.
- Backend/log/DB confirmation: one provider request/session per authored turn, exact Agent fields,
  activity parts, run states, tool/file evidence, and route models agreed with the visible UI.
- Final model/runtime wording check: the UI and source both identify Main as GlassHive / Codex /
  GPT-5.6 Sol, medium, LIFE, full access; LiveKit is still Voice LLM.
- Substitution check: user-path evidence is primary. Tests, source, logs, DB, SDK calls, and model
  review support but do not replace the browser, desktop, Telegram, or call evidence.

## Automated Evidence

- Parent release suite: `914 passed, 3 skipped, 2 failed` in one broad Python 3.11 run. One failure
  was runner-only (`pip` metadata absent in that test environment) and passed in the owning voice
  environment; the other is the pre-existing repository-wide evidence-template migration across
  unrelated legacy reports. All GlassHive provider-owned release tests pass.
- GlassHive full runtime suite: 100% passed after provider behavior and patched-lock changes. Focused
  conversation/MCP suites also passed on the final lock.
- LibreChat affected API: `157/157`; affected client: `47/47`; package and production client builds
  passed. Known unrelated package TypeScript warnings remain visible.
- Telegram: `323 passed`. Voice gateway: `341 passed` plus `48` subtests.
- Playwright installed acceptance: `37/37` assertions.
- Quality + Performance before quota exhaustion: direct `7/7` (p50 3096 ms, p95 4083 ms),
  GlassHive Codex `7/7` (p50 7667 ms, p95 10905 ms), and GlassHive Claude `7/7`
  (p50 11962 ms, p95 26012 ms). The final three-repetition like-for-like rerun passed direct
  `15/15` (p95 4963 ms) and GlassHive Claude `15/15` (p95 25616 ms); Codex stopped after one
  precise `429` and spawned no remaining doomed runs. Native file/shell capability passed on Claude;
  direct was truthfully classified unsupported rather than equivalent.
- Long-run/load: 808.54 seconds; interactive health sampling p95 11 ms/max 27 ms; reserved
  conversation completed while mission capacity was occupied.
- Dependency audit: the tested locked dependency refresh reduced findings from 61 advisories in 14
  packages to 11 in 4. Remaining FastMCP findings concern unused Windows installer/GitHub OAuth
  paths; Starlette fixes require an incompatible major and the shipped endpoint is loopback and
  token-authenticated;
  diskcache/lupa report no available fix.

## Source, Build, Pin, and Installed Alignment

- LibreChat ref: `058f6cb2eb626e664964507f5d5397188bd765e2`.
- GlassHive ref: `1a407a4e90ceea7cd9febcf56b0759ff46f35af0`.
- Parent manifest pins both exact refs; the fresh installer fetched the same commits.
- Generated config registered `glasshive-harness`, both exact models, capability metadata, provider
  authentication, canonical LIFE/full defaults, and the normal custom endpoint.
- A required Main-only A/B/C drift review preceded the live model sync. Unrelated user-managed prompt,
  tool, and cortex drift stayed untouched; other Agents were not mass-migrated.

## Canonical LIFE and Legacy Import

- The owner-private legacy source was inventoried and compared before and after import; the source
  manifest was unchanged, with zero added, removed, or changed entries.
- The private routing audit copied only approved exact files and safe relative symlinks into the
  canonical structure with zero overwrites or checksum failures. Duplicate and secret-risk material
  was excluded.
- `CURRENT.md`, a legacy import index, provenance, and `sources.yaml` expose the organized result.
  Runtime logs/transcripts, `.git`, harness scaffolding, and Claude/Codex-specific prompt files are
  absent from LIFE.
- Exact owner inventory counts, names, paths, manifests, and byte totals remain private and are
  intentionally omitted from this public acceptance report.

## Security Review

- Provider, MCP, and runtime-admin credentials are pairwise distinct and rejected on the wrong route.
- Authenticated owner delegation/full access are server grants; cross-owner Responses continuation is
  forbidden.
- Split-stream redaction occurs before external stream/persistence.
- Patch-compatible Python runtime upgrades were tested before adoption. No dependency was added to
  LibreChat, and no automatic broad audit fix was applied.
- The remaining advisory set is recorded rather than hidden; it is not reachable through the shipped
  local provider path described above and remains dependency-upgrade debt.

## Claude Review

- Status: `COMPLETE; FINDINGS REMEDIATED`.
- The first full-context Opus 5/max review exhausted its 40-minute allowance without an artifact.
  A tighter evidence-indexed Opus 5/max retry completed and correctly identified the startup Main
  rewrite, queued-cancel, terminal-answer, debug-log, streaming-truth, redaction, status-probe, LIFE
  symlink, and QA-evidence gaps now being remediated and rerun.

## Findings

- Fixed during acceptance: complete instruction preservation, clean Claude workspace behavior,
  capacity hot-spin/startup recovery, duplicate schema-tool binding, Feelings exactly once, final
  answer/activity separation, active failure-state cleanup, Responses portability, provider/MCP
  credential separation, installer status truth, canonical LIFE template completeness, and global
  schedule isolation for noncanonical clean installs.
- Regression found and fixed: Codex's native phrase `usage limit` was not included in structured
  rate-limit evidence, causing a generic `502`. Both universal API surfaces now preserve `429`
  semantics in non-stream and stream forms.
- Independent debt: unrelated legacy QA reports fail the broad evidence-template migration; inherited
  LibreChat dependency advisories and the four scoped Python package families remain visible.
- External follow-up: refresh or reauthenticate the Codex CLI account after provider quota becomes
  available, then rerun the repeated Codex slice. This is an availability check, not an unimplemented
  product path; the exhausted-quota behavior is itself accepted and regression-covered.

## Public-Safety Review

- Committed files contain no private prompts, chats, raw outputs, credentials, user identifiers,
  hostnames, screenshots, private absolute paths, or App Support state.
- QA prompts and fixtures are synthetic. Raw outputs and import manifests remain in private local
  state outside repositories and LIFE.
- Public docs use portable paths/placeholders. Nested commits use approved public-safe identities and
  were pushed only to `origin`.

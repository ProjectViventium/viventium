# Telegram Reconciliation and Fallback Recovery QA — 2026-08-06

## Outcome

`GCP-019` and `GCP-021` are **PASS** for the installed local-prod runtime. Controlled ownership loss
on a real running Codex-backed Telegram turn became an exact structured, retryable
`provider_temporarily_unavailable` failure and completed the same Telegram turn exactly once through
GlassHive / Claude Opus 5 at high effort. Telegram displayed the exact requested reply and normal
audio delivery, with no `Connection error. Please retry.` bubble. A real browser turn also stayed live
through reconciliation from a second service process sharing the same runtime state, while explicit
Stop remained cancelled and did not fall back.

The Agent fallback remains distinct from GlassHive's optional provider-internal fallback. The
shipped built-in Agent bootstrap and generated/live model registry use
`glasshive-harness / claude-code:opus / high`; the provider-internal option remains configurable and
disabled by default. No commit or push was made.

## Root cause and repair

The escaped failure was a cross-process race, not exhausted fallback quota:

1. A host CLI was still running and later exited successfully.
2. A second GlassHive service instance shared the same store/runtime root but could not see the
   owning process's in-memory `Popen` map.
3. Reconciliation therefore marked the live run orphaned/interrupted.
4. The owning processor later wrote `completed` unconditionally, overwriting the terminal state.
5. Provider sync treated every interruption as cancellation. LibreChat correctly refuses fallback
   after user cancellation, so Telegram received a generic connection error.

The first PID-only repair was not sufficient: a surviving child or reused PID could still pin a run
after its service owner died, and an exact structured error code could be collapsed by LibreChat's
generic completion classifier. Both boundaries are now explicit.

The repaired runtime now:

- preserves a foreign host run only when the active session matches the run id, its owner-service PID
  is live, and its matching `running` heartbeat is fresh;
- permits a short fresh-heartbeat finalization lease after child exit, but rejects a dead owner,
  stale heartbeat, mismatched run, or reused PID and terminates an ownerless surviving child;
- uses compare-and-set for processor success and error outcomes, so neither late success nor late
  failure can overwrite a terminal run;
- classifies a genuine missing host process as structured, retryable provider loss;
- passes exact supported structured provider codes through LibreChat's completion classifier;
- maps involuntary structured interruption to provider failure while preserving explicit user Stop
  as cancellation with no fallback;
- attaches cancellation capability using the declared GlassHive endpoint even after internal
  transport normalization;
- reconciles a lazily materialized fallback with the resolved primary graph so stale Agent edges do
  not leak into the fallback attempt;
- discovers a service-visible Claude executable under the current user's `.local/bin` and emits it
  into generated runtime config.

## Real user-path QA

### Foreign reconciler during a live browser turn

- Started a synthetic browser chat turn that kept the host CLI active for 120 seconds.
- While the request was `running`, started a separate service object against the same live database
  and runtime root and invoked full reconciliation.
- The foreign runtime validated the matching run id, live owner PID, and fresh heartbeat. The run
  remained `running`; no false orphan transition occurred.
- The same turn was then used for the explicit Stop check below.

### Explicit browser Stop

- Pressed the visible **Stop generating** control on that still-running browser turn.
- The provider request persisted as `cancelled`, its run as `interrupted`, with zero output and the
  operator-interrupt reason.
- No attempt-scoped fallback request was created. After full-page reload the stopped state remained
  visible, the connection-error text was absent, and the browser console reported zero errors.

### Native Telegram primary and fallback recovery

- Sent a clean marker through Telegram Desktop after the installed runtime restart. Telegram showed
  the exact response and normal audio delivery; GlassHive recorded a completed Codex/GPT-5.6 Sol
  primary run.
- Sent a second marker and injected a structured `provider_rate_limited` terminal state through the
  live store only after the real Codex request was running. No source hook or prompt-matching runtime
  branch was added.
- LibreChat created exactly one distinct `main-fallback:` attempt. The primary remained failed with
  zero output; the fallback completed through `claude-code / opus`.
- The Claude action audit recorded `--model opus`, `--effort high`, exit code zero. Native stdout
  identified `claude-opus-5` and returned the exact marker.
- Telegram visibly showed that exact marker plus normal audio delivery, with no generic connection
  error.
- Started a third real Telegram turn whose Codex worker was still running. Through a separate live
  service instance, changed only that synthetic turn's durable owner PID to an already-exited process
  and invoked normal reconciliation. No source hook, prompt branch, or mocked provider response was
  used.
- Reconciliation immediately classified the zero-output primary as structured/retryable
  `provider_temporarily_unavailable`, terminated the ownerless child, and cleared the active session.
  The late owner-side processor result lost its state compare-and-set and could not overwrite the
  interruption.
- LibreChat preserved the exact structured code and created exactly one fallback attempt. Its Claude
  audit recorded Opus 5, `--effort high`, and exit zero; Telegram visibly delivered the exact reply
  plus normal audio with no connection-error bubble.

### Installed runtime and cleanup

- Supported activation/restart completed from the current checkout.
- LibreChat API, LibreChat web, modern playground, and GlassHive health each returned HTTP 200.
- The authenticated GlassHive registry exposed only `codex-cli:gpt-5.6-sol` (recommended medium) and
  `claude-code:opus` (Claude / Opus 5, recommended high), both ready.
- A fresh supported live-Agent pull verified all 13 installed built-in Agents (Main, 11 background,
  and one handoff) use `glasshive-harness / claude-code:opus / high` for Agent fallback. The broader
  compare also showed unrelated protected live/source drift, so no broad sync was performed.
- Active Viventium config/template/runtime surfaces contained no configured Opus 4.8 or Sonnet 4.5
  route.
- The disposable browser user and all its conversations/messages were removed through LibreChat's
  supported deletion command; direct database counts confirmed zero remaining records. The browser
  session was closed. Screenshots and raw runtime evidence remain private outside the repository.

## Automated evidence

- GlassHive API, conversation-provider, and host-runtime suites: 404/404 selected tests passed.
- Focused cross-process ownership, owner heartbeat/finalization lease, dead-owner child cleanup,
  stale/reused PID, late success/error compare-and-set, involuntary interruption, cancel-wins, and
  run-scoped cancel regressions passed.
- LibreChat provider, fallback, graph, request-persistence, callback, and client selection: 225 tests
  passed across six affected suites.
- Config compiler suite: 152 tests passed, including service-visible Claude executable discovery.
- Compiler, source-of-truth, GlassHive source, installer, component manifest, generated config, and
  active runtime scan found no configured Opus 4.8 or Sonnet 4.5 route.

## Independent review

A final review-only Claude Desktop pass returned **GO for this incident; no remaining blockers**.
It independently reran the three GlassHive suites (404/404), inspected the exact structured-code
passthrough and lease/cleanup tests, confirmed the final source is active in the installed runtime,
and confirmed the 13 built-in live Agents use the intended fallback tuple. It did not modify files,
git state, runtime state, or data.

The reviewer recorded non-blocking hardening follow-ups outside this incident's acceptance gate:
finish scheduled-occurrence bookkeeping when a late processor loses its terminal compare-and-set;
add a periodic/event-driven reconcile for an exceptional owner/heartbeat grace edge; bind cleanup to
a process start-time identity before signaling a recorded PID; and make the temporary-unavailable
message more precise if both the primary and fallback fail.

## Acceptance matrix

- Normal installed Telegram primary: **PASS**.
- Structured rate-limit to Opus 5/high in the same Telegram turn: **PASS**.
- Structured dead-owner loss to Opus 5/high in the same Telegram turn: **PASS**.
- Foreign reconciliation while another process owns a live host CLI with a fresh lease: **PASS**.
- Dead owner/live child cleanup and stale/reused PID rejection: **PASS**.
- Late success and late error cannot overwrite durable interruption: **PASS**.
- Explicit user Stop remains cancelled and never falls back: **PASS**.
- Browser persistence/reload and console: **PASS**.
- Installed runtime restart and health: **PASS**.
- Disposable QA data cleanup and public/private boundary: **PASS**.

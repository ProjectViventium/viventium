# Parallel Work QA

This folder is the living acceptance source for account-wide Parallel Work, authoritative Active
Work visibility, bounded durable GlassHive concurrency, native worker teams, and cross-surface
delivery/control.

Use `PWK-NNN` case IDs. Record dated public-safe evidence under `reports/`. A release report must
correlate the visible user result with GlassHive/Core state, logs, callbacks, delivery rows, compiled
configuration, and the installed runtime artifact.

Owning requirements are
[`55_Parallel_Work_Orchestration.md`](../../docs/requirements_and_learnings/55_Parallel_Work_Orchestration.md),
[`48_GlassHive_Workstation_Sandbox_Runtime.md`](../../docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md),
[`09_Agent_Streaming_Usage.md`](../../docs/requirements_and_learnings/09_Agent_Streaming_Usage.md),
and the callback/scheduler/surface requirements linked from those sources. Required user surfaces are
Telegram Desktop, Playwright Web, audible Voice, Scheduler, GlassHive, MCP/API, installer/CLI, and a
fresh installed runtime.

The quality bar is one responsive Main plus durable, truthful, isolated missions: no dropped rapid
input, no worker impersonation, no phantom acknowledgement, no cross-owner or cross-process authority,
no hidden stale/queued work, and no latency regression on focused turns. The deployment flag remains
off and the default remains `focused` while any release-blocking case is not fully passed.

## Current acceptance status — 2026-08-16

The feature remains dark and is not release-ready. The 36-case catalog currently has four PASS,
19 PARTIAL, zero FAIL, and 13 NOT RUN cases. `PWK-018` now passes exact source/pin/build/install/runtime
parity; `PWK-026` passes clean seed/reseed and live restart; `PWK-031` passes the independent
Direct/Codex/Claude quality bank; and `PWK-035` passes canonical new-chat route, cache, retry identity,
and headed reload continuity.

A brand-new public installer run now proves the exact pushed parent and nested component commits,
generated local GlassHive API/MCP/UI origins, compiled client/package artifacts, healthy running
processes rooted in the clean checkout, and the dark/focused default. The input omitted the runtime
port override; the compiler derived the non-default bind and an authenticated account-API read
returned 200. That run caught three
public-safety defects before acceptance: LibreChat logged the interpolated custom config, both
launchers printed the LiveKit key or its prefix, and an invalid short LiveKit secret caused the native
server to log the key identifier. All three are regression-guarded and fixed. The final scan covered
13 persisted service logs plus the launcher stream and found no full config, private instructions,
configured credential value, or duplicate package key; every isolated listener closed after teardown.

Current headed Web evidence also proves account preference toggle and reload persistence. A disabled
deployment hid new-admission UI without hiding the retained failed work card; Dismiss stayed available
and remained effective after reload. This makes installed rollback `PARTIAL`, not complete: no
provider-backed mission was running, so running-work controls, callbacks, delivery, capacity reduction,
Telegram, and Voice rollback parity remain.

Current real-surface evidence now includes Telegram Desktop toggle/restart persistence, roster,
Message, Queue, Resume, truthful unavailable Pause, Stop confirmation, and Dismiss. A real Docker
mission-boundary probe passed ambient-authority, protected-state, mount, Docker-socket, metadata,
raw-egress, sibling-peer, proxy-health, and unauthorised-broker checks. The clean-room source uses
per-mission internal networks, exact full proxy/worker profiles, exact-generation startup, and
invocation-local tmpfs grant projection; the complete current GlassHive runtime suite collected
1,427 tests and passed with ten intentional opt-in live-environment skips. Those native CLI cases
also passed separately against the installed Codex/Claude CLIs, and Glass Drive UI passed 113/113.

One escaped live scheduler defect was found and fixed: needs-input workers with queued follow-ups
could repeatedly resubmit processors. Non-dispatchable workers are now excluded at query,
resubmission, and direct admission boundaries. Focused RED-to-GREEN and the complete API module pass,
and the restarted runtime remains near idle instead of saturating multiple cores.

Performance and idempotency supporting evidence also improved. Focused/known-empty turn setup made
zero user, roster, network, or model calls at 0.001 ms p95. Authenticated active-work reads measured
9.130 ms p95 and 39.457 ms maximum. One synthetic durable delegation committed in 40.926 ms; 20
lost-response replays were stable at 5.666 ms p95 and yielded exactly one delegation, worker, and
run. Missing authorization became explicit nonretryable needs-input before provider start, with zero
active lease.

The current explicit local host-Codex path now projects the owner-local CLI authorization baseline
without weakening automatic clean-room or enterprise isolation. A real installed-CLI root mission
authenticated, completed, and persisted its native session. Repeated child-directed probes did not
emit a real child lifecycle, so Codex child capability remains false and the native-team case stays
PARTIAL.

The corresponding explicit local host-Claude path also now uses access-only owner authorization,
never forwards refresh authority, and requires server-owned authorization in enterprise mode.
Current installed-CLI root, resume, and plugin-isolation smokes pass; background-session roster,
restart, targeted native controls, and recursive Stop still keep the Claude case PARTIAL.

Real running-root Stop/restart probes now also pass for installed Codex and Claude: each exact run
settled `interrupted`, and a fresh service instance preserved terminal truth without resurrecting a
PID. The current Claude CLI also projected one real child lifecycle; Stop while the child was live
reached zero active children and remained terminal after restart. Visible topology, unrelated-session
isolation, targeted native Message, and real Codex child projection remain.

The post-fix headed Web A/B/quick-C run now retains one substantial ask and one durable card for each
of Alpha and Beta, answers quick C with exact `BLUE`, and survives canonical-URL reload. Both missions
truthfully require input because the synthetic account still needs a provider reconnect. Successful
running Pause/Steer, remaining audible controls, scheduler fanout, three-way and maximum-load
concurrency, real owner isolation, and running-mission rollback remain. See the
[latest install/rollback report](reports/2026-08-16-release-candidate-install-and-rollback.md), the
[current-candidate report](reports/2026-08-15-current-candidate-progress.md), and the historical
[Web report](reports/2026-08-13-live-web-account-and-delegation.md).

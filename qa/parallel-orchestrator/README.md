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

The plain-language
[Queen Bee and Worker Bee contract](../../docs/requirements_and_learnings/55_Parallel_Work_Orchestration.md#locked-queen-bee-and-worker-bee-user-experience)
is normative and mapped to required guards at the top of [`cases.md`](cases.md). The Bee names are
aliases for Main and durable GlassHive missions, not new runtime layers.
Full ability parity is release-blocking: `PWK-011` and `PWK-UC-019` compose the owning Voice
(`MPV-061`), file input/output (`TGDOC-010`), memory/recall, capability-broker, artifact-delivery,
fallback, control, and restart cases. A pass in one narrower feature lane cannot close that gate.

## Installed journey verifier

`scripts/installed_journey_qa.py` is the fail-closed evidence runner for `PWK-UC-014` through
`PWK-UC-019`. Run the real installed Telegram, browser, Voice, restart, fault, and isolation steps
first. Store private proof under the configured App Support QA evidence root, then run:

```bash
python3 qa/parallel-orchestrator/scripts/installed_journey_qa.py \
  --case-id PWK-UC-014 \
  --manifest <private-journey-manifest.json> \
  --evidence-root <private-evidence-root> \
  --artifact-identity <installed-parallel-work-artifact-identity.json> \
  --receipt-manifest <private-receipt-manifest.json>
```

The runner requires the exact case checklist, candidate/artifact identity, fresh hashed evidence,
and the case-specific minimum real-surface proof. It cannot turn a mock, source test, missing UI,
or self-declared partial result into `PASS`. Feed its private receipt manifest to
`bin/viventium qa-evidence record` only after the runner returns `PASS`.

## Current acceptance status — reconciled 2026-08-30

The feature remains dark and is not release-ready. The 50-case catalog currently records 13 PASS,
25 PARTIAL, and 12 NOT RUN cases. `PWK-026` passes clean seed/reseed and live restart;
`PWK-031` passes the independent Direct/Codex/Claude quality bank; `PWK-035` passes canonical
new-chat route, cache, retry identity, and headed reload continuity; and `PWK-037` passes the exact
account-aware startup/admission boundary through an installed Telegram mission, terminal callback,
runtime recovery, and reloaded Web state. `PWK-002` now passes the installed rapid A/B/C accounting
and Main-availability branch, while `PWK-038` locks the durable-receipt/presentation lifecycle that
keeps a committed mission from turning into stale inline authorship or a hung response.

The 2026-08-18 installed proof produced two exact durable mission acknowledgements and a separate
quick answer while the second substantial turn was still authoring. A full Web reload retained the
same independent work: one PDF was completed/delivered, and the remaining work was truthfully queued
for host capacity with controls. This closes the basic rapid-input product use case without claiming
the separate three-way execution, maximum-load, Voice, owner-isolation, clean-install, or rollback
gates. See the
[rapid Main-availability report](reports/2026-08-18-rapid-main-availability.md).

The latest installed provider-backed proof also closes the earlier single-mission terminal gap:
Main stayed responsive while one durable mission ran, guidance persisted as Message, explicit Retry
resumed the same workspace after provider reauthorization, capacity queued rather than failed, an
11-page PDF opened visibly in Preview, and one useful Main-authored completion reached Telegram and
remained completed/delivered after Playwright reload. Broader rapid A/B/C concurrency and release
gates remain. See the
[installed Telegram mission report](reports/2026-08-17-telegram-provider-backed-mission.md).

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
concurrency, real owner isolation, component commits and pins, installed artifacts, clean install,
and rollback remain. See the
[current-candidate report](reports/2026-08-15-current-candidate-progress.md) and the historical
[Web report](reports/2026-08-13-live-web-account-and-delegation.md).

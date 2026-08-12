# Prod And Dev Runtime Isolation QA — 2026-08-10

## Outcome

**PARTIAL.** Local prod and the synthetic anti-QA dev environment coexisted with separate app-facing
and mutable-state ownership. The supported QA stop removed only QA-owned services and left every
measured prod identity unchanged. A later supported stop/start restored the isolated runtime, but
the retained logs do not contain the earlier exact-listener adoption event, so the complete
start -> adopt -> stop -> start lifecycle is not release evidence yet.

No raw PID, container ID, private page content, screenshot, account identifier, hostname, or local
absolute path is included in this public report.

## Acceptance Evidence

| Contract                                   | Evidence                                                                                                                                                                                                   | Result |
| ------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ |
| Compiler-owned Workbench isolation         | `prompt_workbench_port` is a first-class profile/config port and receives the dev offset; explicit overrides remain authoritative.                                                                         | PASS   |
| State + PID + port ownership               | Prod and QA Workbench used different App Support state, recorded PIDs, and ports. Both visible pages were distinct, and both watchdog PIDs stayed stable during the coexistence window.                    | PASS   |
| Wrapper-owned dev identity and strict stop | The supported wrapper supplied dev scope before compile; stop recompiled the named dev config and required compiled dev identity before cleanup.                                                           | PASS   |
| Dev owns its Workbench sidecar             | Supported QA stop closed the QA Workbench and its other QA listeners without invoking workspace-wide cleanup.                                                                                              | PASS   |
| Local RAG isolation                        | The QA-local RAG stack used an offset vector host port and a dev-specific Compose project. QA stop removed only that project.                                                                              | PASS   |
| Prod survives QA stop                      | Prod API, web, playground, GlassHive, and Workbench PIDs were unchanged after QA stop. Prod RAG container IDs were also unchanged.                                                                         | PASS   |
| Native PID identity                        | MongoDB, Meilisearch, and LiveKit stop paths validate the live process identity before signalling a PID and discard stale mismatches safely.                                                               | PASS   |
| Post-fix adoption lifecycle                | Current state proves a later supported stop/start restored exact selected-runtime native listeners while prod stayed healthy. No durable log or ledger preserves the preceding exact-listener adoption event. | PARTIAL |

After the supported QA stop, all QA-owned ports and QA Compose containers were closed. No prod
listener or prod RAG container was restarted or replaced.

## Automated Evidence

- Config compiler: **168/168 passed**.
- Stable-dev-runtime plus native-stack baseline: **61/61 passed** before the latest focused
  Workbench regression addition.
- Focused Workbench/compiler ownership regressions after that addition: **10/10 passed**.
- Final native/runtime isolation gate after the escaped ownership fixes: **72/72 passed**; the
  public-safety gate also passed.

The counts above are stated in their actual run order. The final 72-test gate includes the current
native ownership and selected child-environment regressions; the earlier 61-test number is retained
only as historical run-order evidence.

## Regression Gate

Rerun `SDR-013` whenever dev port compilation, App Support/state roots, Prompt Workbench lifecycle,
stack stop ownership, local RAG Compose naming/host ports, or native PID matching changes. Automated
tests and health responses are supporting evidence; release acceptance still requires the real
coexistence sequence, two visible Workbench surfaces, the supported dev stop, and pre/post prod
identity comparison.

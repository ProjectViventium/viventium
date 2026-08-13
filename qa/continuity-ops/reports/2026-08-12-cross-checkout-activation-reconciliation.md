# Cross-Checkout Activation Reconciliation — 2026-08-12

## Outcome

PARTIAL pending the post-fix supported activation. The reviewed candidate reached its API and
loaded both configured Google Workspace account slots, but the detached-start watcher restored the
predecessor after matching an explicitly nonblocking local-search parity warning as a generic
failure.

## Root Cause And Fix

The launcher correctly reports incomplete search-index parity as visible degraded state and
continues frontend startup. The outer watcher previously matched any Viventium log line containing
`failed`, contradicting that contract. The watcher now excludes only the exact structured
nonblocking warning; real dependency, build, required-port, and other Viventium failures remain
terminal.

## Evidence

- RED: the focused classifier test returned terminal for the exact nonblocking warning.
- GREEN: the same warning is nonterminal while existing required-surface and build-error cases
  remain terminal.
- The supported activation is the final gate. Its result must include exact checkout/component
  provenance, healthy required surfaces, and preservation of the visible search-parity warning.

Raw runtime logs, search counts, account state, user paths, and credentials remain outside this
public report.

# Native Feelings navigation QA — 2026-07-19

Status: **PASS for the running-stack user path and installed helper artifact; PARTIAL for the full
stopped-stack start-and-open continuation.**

All installation state and stopped-state controls used a synthetic isolated user root. The user's
installed helper and active stack were restored after the run. No private desktop screenshot,
account value, raw conversation, credential, hostname, or machine-local path is published here.

## Scope under test

- Source: the isolated `codex/feelings-status-navigation` worktree based on the current public core
  baseline.
- Product change: a first-level `Open Feelings` item in the native macOS V menu, plus a reusable
  path-aware browser opener and a stopped-state `Start and Open Feelings` continuation.
- Delivery surfaces: Swift source, rebuilt universal prebuilt helper, prebuilt source checksum,
  clean isolated installation, and the installed/signed app artifact.
- Owning requirement: `docs/requirements_and_learnings/54_Emotional_Cortex_And_Feeling_State.md`.

## User-path evidence

| Path | Actual action and visible result | Supporting evidence | Result |
| --- | --- | --- | --- |
| Healthy stack | Opened the real native V menu. It contained `Open`, `Open Feelings`, `Stop`, `Running`, `Advanced`, and `Quit`. Clicking `Open Feelings` created a browser tab titled `Viventium Feelings`; the live core Feelings surface loaded. | Accessibility menu enumeration, browser accessibility tree, and HTTP `200` from the supported `/feelings` entrypoint. | **PASS** |
| Stopped stack | Re-launched the isolated installed helper against closed synthetic ports while a synthetic CLI-operation lock prevented automatic startup. The menu truthfully showed `Start` and `Stopped`. Clicking `Open Feelings` displayed `Viventium is not running`, `Start Viventium now and open Feelings in your browser?`, and buttons `Start and Open Feelings` / `Cancel`. | Native accessibility enumeration plus helper log state. The confirmation was cancelled to avoid launching a second heavy stack beside the user's active runtime. | **PARTIAL**: the stopped prompt and continuation wiring are proven; the subsequent full-stack launch/open was not exercised live. |
| Existing generic action | Inspected the same menu before and after the change. `Open` remains the first generic destination and `Open Feelings` is additive. | Native menu enumeration and source contract test. | **PASS** |
| User environment restoration | Terminated the isolated helper and reopened the user's original installed app. | Process path check proved only the original installed helper remained. | **PASS** |

## Build and automated evidence

| Gate | Result |
| --- | --- |
| Swift source typecheck | **PASS** |
| Focused release tests (the Feelings SOT doc guard plus `feelings_navigation_contract`, `macos_helper_install`, and `native_stack_helpers`) | **22 passed, 0 failed** |
| Rebuilt helper architecture | **PASS**: universal `x86_64` + `arm64` |
| Clean isolated installer selection | **PASS**: installer selected the shipped prebuilt |
| Installed artifact signature | **PASS**: valid on disk and satisfies its designated requirement |
| Installed artifact strings | **PASS**: `Open Feelings`, `Start and Open Feelings`, and `/feelings` present |

## Traceability and honest boundary

`native V menu -> Open Feelings -> /feelings -> live Feelings surface` is proven through the real
installed helper and browser. `stopped -> confirmation -> startStack(openPath: "/feelings")` is
covered by the source contract and the real native confirmation, but a second complete Viventium
stack was not started during this run. `EMO-038` and `EMO-UC-028` therefore remain **PARTIAL**, not
relabeled as complete.

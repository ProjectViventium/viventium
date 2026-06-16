<!-- qa-evidence-exempt: legacy sanitized RCA/QA note retained for historical context; current acceptance must use cases plus a fresh v2 report. -->

# 2026-06-08 Scheduled Trigger Receipt QA

## Summary

- Result: PASS for source and synthetic scheduled-shape proof; PENDING LIVE for the next real
  overnight scheduled receipt.
- Scope: memory-hardening scheduled trigger observability and nightly QA classification.
- Related cases: `MEMHARD-010`, `MEMHARD-UC-011`.

## Requirement

Memory hardening is local maintenance, not a Prompt Workbench scheduled prompt. The macOS scheduled
maintenance lane must prove itself with a public-safe trigger receipt, while the Workbench nightly
reflection remains on its documented chain:

`scheduled prompt -> filled placeholders -> GlassHive run -> callback -> scheduler ledger ->
Workbench shows completed`.

## What Changed

- The installed memory-hardening LaunchAgent command now passes an explicit scheduled trigger marker
  to the memory-hardening wrapper.
- Scheduled wrapper invocations write a redacted trigger receipt before model work starts and
  finalize it with status, exit code, timing, timezone-at-fire, and optional run id.
- Manual wrapper runs without a trigger marker do not create a scheduled trigger receipt.
- Power-budget skips finalize the receipt as `skipped` with a public-safe reason.

## Evidence

- Focused memory-hardening contract tests: `47 passed`.
- The live installed LaunchAgent was refreshed through the supported schedule installer, then
  inspected read-only. Its direct wrapper command includes the explicit scheduled trigger marker,
  retains the daily local `03:00` schedule, uses the App Support working directory, and is not
  currently running.
- Read-only memory-hardening status still shows the latest prior hardener run as successful. No
  model-backed hardening or transcript ingest was forced for this QA.
- New regressions cover:
  - explicit LaunchAgent `launchd` trigger marker;
  - public-safe trigger receipt creation/finalization;
  - manual-run separation;
  - scheduled power-skip receipt finalization.
  - dry-run-first scheduled fires preserving both the requested command and the actually executed
    dry-run command in the receipt.

## Acceptance Logic

Nightly QA should classify memory hardening as `PASS` or healthy `SKIPPED` when:

- the active LaunchAgent matches the generated schedule;
- the scheduled trigger receipt exists and identifies the scheduled source;
- the hardener run summary or skip reason is healthy;
- provider, transcript, vector, and eligibility evidence do not show errors.

Nightly QA should reserve `PARTIAL` or `FAIL` for:

- missing receipt after due/grace;
- duplicate or conflicting trigger evidence;
- active LaunchAgent/config mismatch;
- failed hardener run;
- provider/model/vector/runtime errors;
- unknown eligibility or unexpected empty selection.

UTC differences from travel, DST, launchd wake coalescing, or audit-time timezone context are not
by themselves degradation.

## Remaining Live Gate

The next real scheduled memory-hardening window must prove a live receipt correlated with the
installed LaunchAgent and the hardener run summary. This report does not claim that future scheduled
receipt has already occurred.

## Claude Review

Claude review-only agreed the fix is aligned with the documented split: Prompt Workbench scheduled
prompts stay on the Scheduler/GlassHive/callback/Workbench chain, while memory hardening remains
local macOS maintenance. It flagged one clarity gap: a dry-run-first scheduled fire requests
`apply` but actually executes `dry-run`. The wrapper now finalizes receipts with both the requested
command and the executed command, and a regression covers that path.

## Public Safety

This report contains no raw prompts, transcripts, memory values, account identifiers, local paths,
tokens, callback payloads, screenshots, or private runtime dumps.

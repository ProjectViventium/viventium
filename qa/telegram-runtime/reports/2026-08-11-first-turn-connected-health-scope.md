# Telegram first-turn connected-health scope — 2026-08-11

## Result

PASS for the escaped Telegram/conversation-provider failure. PASS-AUTOMATED for the shared grant,
fallback, and background-cortex lifecycle fixes; PARTIAL-CROSS-SURFACE because the browser voice
gateway and scheduler were not rerun as real users in this pass. PARTIAL for restoring the newest
WHOOP acquisition: the historical archive is readable, but WHOOP rejects the current rotated
refresh grant and fresh provider consent could not be completed because the requested Chrome
control connection was unavailable.

## Root cause

Telegram begins a new conversation with provisional request identity. The conversation-provider
capability refresher retained that early body even after Agent run creation assigned the durable
conversation and response message ids. It therefore signed a grant without exact turn scope. The
production broker correctly rejected the grant, and the provider harness improvised a browser path
and falsely presented that broker failure as upstream WHOOP authorization trouble. WHOOP had not
been called on the failed turn.

A separate connector condition was also confirmed: the latest scheduled archive run could not
refresh its WHOOP grant. The official token endpoint rejected the stored rotated refresh grant with
HTTP 400. There is one private token file and one loaded schedule, so no duplicate local scheduler
or state-root race was found. The old append-only archive remains readable.

## Fix

- Provider refresh now receives the finalized per-run request body and signs the durable
  conversation/message scope.
- Minting now rejects provisional/truly unscoped grants before a token, resource record, or signed
  provider header can be produced.
- Provider fallback keeps the owning participant's structured MCP authority, and background cortex
  execution installs invocation-fresh refresh before its Agent run.
- The health connector now emits one authorization-recovery flag for both failure lanes. The UI
  shows the existing one-click action for that flag and configured/no-run state; unrelated
  history-import degradation does not offer duplicate consent.
- Requirements and durable QA cases now cover the first gateway turn and stale-grant recovery.

## Evidence actually run

- RED regressions proved both defects: provider refresh received the provisional body with no
  message id, and the degraded UI hid authorization recovery.
- GREEN focused acceptance includes 86 grant/auth/provider/audience tests, 24 Agent-run tests,
  eight Agent-initialization tests, 45 background-cortex tests, 38 Telegram-route tests, 14
  owner/admin health-route tests, seven health API-sanitizer tests, nine WHOOP-card tests, and 51
  Viventium-Health component tests: 282 focused tests passed in total. Two component subtests also
  passed. Two opt-in live-contract tests were skipped in the full component run, then both official
  live-contract checks passed separately.
- Focused client lint and the production-like Vite build passed. The repository-wide TypeScript
  check still reports numerous pre-existing failures in unrelated files and did not name either
  changed WHOOP client file.
- Real Telegram Desktop: a new marked request used the owner-only health MCP four times, returned a
  short dated summary plus the exact current source-sync blocker, persisted as a final response,
  and delivered both text and audio.
- Runtime logs contained grant-scoped discovery reuse, four successful health MCP transport calls,
  no missing-turn-scope warning for the acceptance turn, and an `audio_sent` completion for its
  generated voice reply. The persisted assistant record was neither unfinished nor errored.
- The rebuilt installed health component reports the expected authorization-recovery flag and its
  installed component reference matches the parent manifest pin.

## Not run

- Fresh WHOOP consent and the post-consent forced refresh/daily pull remain blocked by the
  unavailable Chrome control connection. No browser substitute, scraping, token exposure, or
  destructive revoke was used.
- The fresh degraded-state reconnect button was proven by the component test and build but could
  not be visually exercised in the requested Chrome session for the same control-connection reason.
- The real non-owner path was not repeated with a second human account; structural audience and
  broker isolation regressions passed.
- Voice and scheduler gateway turns were not repeated on their real user surfaces; their shared
  finalized-body/fail-closed logic is automated evidence only in this report.

## Public safety

This report contains no health values or bodies, credentials, account or conversation identifiers,
screenshots, usernames, emails, hostnames, or local absolute paths.
<!-- qa-evidence-exempt: Historical or specialized supporting artifact retained without retroactively inventing missing evidence; current release acceptance requires a fresh full-view report. -->

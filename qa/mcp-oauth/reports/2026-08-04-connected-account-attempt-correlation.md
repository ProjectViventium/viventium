# Connected-Account Attempt Correlation QA — 2026-08-04

## Verdict

**PASS.** A pre-existing usable credential no longer closes a newly started OAuth popup. Completion
is correlated to the authenticated user, provider, and new attempt.

## Escaped defect and cause

The settings client polled the saved-key endpoint. A truthy expiry from an older usable credential
looked like completion, so a fresh provider chooser could close before the user selected an account.
Saved credential state and one browser authorization attempt are different facts.

## Fix

- OAuth start returns an unpredictable `attemptId`.
- The client polls the attempt-status endpoint, not saved-key expiry.
- A newer start supersedes an older attempt; stale callbacks, popup messages, and exchanges cannot
  complete or overwrite it.
- Attempt status is authenticated and scoped to user plus provider.
- Process-local attempts expire after 30 minutes. Restart during consent fails safe and asks for a
  fresh attempt.

## Evidence actually run

- Real Chrome, logged-in user surface, installed runtime after rebuild/restart: reconnect opened the
  provider chooser and stayed open beyond the prior false-close window; consent completed; the
  popup closed only after the matching callback; Connected Accounts displayed the saved state.
- Active component API tests: 15/15 pass.
- Canonical component API tests: 14/14 pass.
- Focused client tests: 4/4 pass.
- Active and canonical frontend builds pass.

Private account identifiers, callback values, tokens, and raw screenshots remain outside this
public report.

## Regression contract

Rerun `MCPOAUTH-005` whenever popup polling, connected-account status, OAuth callback exchange,
credential expiry handling, or API restart behavior changes. Source/unit evidence cannot replace
the real browser popup-lifetime and completion check.
<!-- qa-evidence-exempt: Historical or specialized supporting artifact retained without retroactively inventing missing evidence; current release acceptance requires a fresh full-view report. -->

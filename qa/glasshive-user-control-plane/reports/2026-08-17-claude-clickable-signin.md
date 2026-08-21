# Hosted Claude clickable sign-in — 2026-08-17

## Summary

- Result: PASS for the installed clickable sign-in and cancellation path.
- Build/source under test: release and source revisions recorded below.
- Runtime/artifact under test: installed three-service hosted canary.
- Environment: authenticated Microsoft Edge browser and installed GlassHive.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `GHUCP-007` | PASS | One reviewed sign-in action opened the official provider page; cancel and refresh remained actionable | No provider grant or worker mission was claimed |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: personal provider-account setup.
- Requirement: `GH-UCP-005`.
- Use case: open the native Claude sign-in from Connections.
- QA case: `GHUCP-007`.
- Expected result: one clickable reviewed destination with technical output collapsed.
- Actual evidence: installed Edge action, official login page, cancel, refresh, and focused regressions.
- Remaining gap or fix: complete personal authorization and mission were separate later cases.

## Full-View Evidence Checklist

| Evidence surface | Result / sanitized pointer |
| --- | --- |
| Requirement, docs, and nested docs | Requirement 55 and `GHUCP-007` own the path |
| Code, scripts, and automated harness | Runtime URL allowlist, terminal sanitizer, UI server, and control-plane suites |
| Local/external prerequisite state | Installed canary healthy; provider page reachable |
| Logs, DB/state/persistence | No post-readiness critical log; refresh kept the cancelled/reconnectable state |
| Generated/shipped artifact | Exact installed release and source identities recorded below |
| Real user path and visual comparison | Edge Connections -> sign-in -> official page -> cancel -> refresh matched the expected UI |
| Not run / blocked | Authorization grant, mission, and two-owner lifecycle were not run in this report |

## User-Grade Evidence

- Surface exercised: installed GlassHive Connections in Microsoft Edge.
- Real user path: Reconnect -> Open Claude sign-in -> provider page -> Cancel -> refresh.
- Visible outcome: one clickable sign-in action; no raw terminal transcript in the primary view.
- Expanded/detail state: troubleshooting stayed collapsed and the cancelled state exposed Reconnect.
- Persistence/reload result: refresh preserved the honest cancelled/reconnectable state.
- Backend/log/DB confirmation: exact canary health and the post-readiness log window were clean.
- Final model/runtime wording check: the UI reported cancellation, not a completed authorization.
- Substitution check: automated tests, logs, and source inspection support but do not replace the installed Edge path above.

## Scope

This run covers the user-visible provider setup handoff in **Connections**. It verifies that the
native Claude CLI sign-in destination is presented as one normal action instead of an unclickable
terminal transcript.

It does not claim that a Claude authorization grant or personal-Claude worker mission completed.

## Findings

The native Claude CLI now emits its authorization URL on `claude.com/cai/oauth/authorize`. The
runtime's reviewed destination list still recognized older Claude hosts only, so it withheld the
structured setup URL and the UI fell back to raw technical output. The terminal sanitizer also
removed only the introducer of OSC hyperlinks instead of the complete control sequence.

The runtime now:

- accepts only the exact HTTPS `claude.com/cai/oauth/authorize` host-and-path pair;
- continues to reject arbitrary paths on the same host;
- removes complete OSC hyperlink controls while preserving the visible destination once; and
- returns the structured destination to the existing **Open Claude sign-in** action while keeping
  technical output collapsed.

## Installed candidate

- release: `glasshive-20260817-claude-signin-link-32`
- parent revision: `ec659f45f1ba7ca99733e2cc053c81e665cf7b04`
- GlassHive revision: `11a40de9b55f6a7bb35bfe6b1ef7ab3cb03a9999`

The activation helper committed the candidate only after exact local release health, canary edge
release health, unchanged stable-site status, and explicit browser acceptance passed.
All three candidate services remained active; the five-minute post-accept journal window contained
no traceback, critical, or unhandled-exception markers. Four earlier UI `ConnectError` tracebacks
were confined to the bounded service-restart window and did not recur after readiness.

## Real browser result

Run in an authenticated Microsoft Edge profile against the installed hosted development canary:

1. Hard refresh **Connections** and select **Reconnect** for the personal Claude account.
2. Confirm the primary view shows **Open sign-in to continue** and one **Open Claude sign-in** link.
3. Confirm the raw terminal transcript is not present in the primary view and troubleshooting stays
   collapsed.
4. Activate the link and confirm a new tab opens the official Claude login page.
5. Return to GlassHive, cancel the test setup without granting access, refresh Connections, and
   confirm the account truthfully reports that setup was cancelled with **Reconnect** available.

Result: **PASS** for clickable sign-in, safe destination promotion, cancellation, and refresh
persistence. No authorization grant was completed and no provider credential was created.

## Automated Evidence

- Runtime control-plane suite: 34 passed, including exact native URL, arbitrary-path rejection, and
  OSC hyperlink regressions.
- GlassHive UI server suite: 228 passed.
- Parent component-pin and publication inventory suite: 14 passed.
- JavaScript syntax, Python compilation, helper integrity, and parent/nested diff checks: passed.

## Remaining boundary

A complete personal Claude authorization, worker mission, reconnect/forget lifecycle, contention,
and two-owner isolation remain separate acceptance work. This report proves only the corrected
sign-in handoff and does not upgrade those broader lifecycle items from PARTIAL.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots, personal emails, account identifiers, or customer data.
- [x] No conversation, message, session/call, provider-request, or database identifiers.
- [x] No local absolute paths, hostnames, machine names, private stack traces, exports, or runtime dumps.
- [x] Private observations are summarized only as sanitized outcomes and counts.

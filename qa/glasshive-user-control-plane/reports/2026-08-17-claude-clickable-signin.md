# Hosted Claude clickable sign-in — 2026-08-17

## Scope

This run covers the user-visible provider setup handoff in **Connections**. It verifies that the
native Claude CLI sign-in destination is presented as one normal action instead of an unclickable
terminal transcript.

It does not claim that a Claude authorization grant or personal-Claude worker mission completed.

## Root cause and fix

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

## Automated evidence

- Runtime control-plane suite: 34 passed, including exact native URL, arbitrary-path rejection, and
  OSC hyperlink regressions.
- GlassHive UI server suite: 228 passed.
- Parent component-pin and publication inventory suite: 14 passed.
- JavaScript syntax, Python compilation, helper integrity, and parent/nested diff checks: passed.

## Remaining boundary

A complete personal Claude authorization, worker mission, reconnect/forget lifecycle, contention,
and two-owner isolation remain separate acceptance work. This report proves only the corrected
sign-in handoff and does not upgrade those broader lifecycle items from PARTIAL.

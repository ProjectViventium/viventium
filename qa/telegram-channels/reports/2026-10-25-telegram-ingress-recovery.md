# Telegram saved-input notice — 2026-10-25

## Summary

QA: blast-radius. Result: **SCOPED PASS** for the retained-input notice adapter.

The [Telegram requirements](../../../docs/requirements_and_learnings/03_Telegram_Bridge.md)
and `ingress-outage-and-idle-typing` [journey](../cases.yaml) require truthful outage wording
without replaying accepted work.

## Scope Run

When Core returns HTTP 503 with a valid saved-input receipt in `preparing`, `ready` or
`admitted` state, Telegram replies to the exact current message: “Your message is saved.
Viventium will reply when the local service is ready.” The notice uses the existing transport
path. It does not start Main, speech, typing or a fresh execution retry.

Terminal receipts, incomplete receipts, ambiguous failures and obsolete inputs do not produce
this notice. Proven failures before intake retain the existing retry notice.

The reconciled change contains only the adapter's receipt classification, wording and current
source gate, plus its causal regression checks. It preserves newer main source. This report
does not certify separate LibreChat input storage, parent ordering or recovery changes.

## Automated Evidence

| Contract | Actual evidence | Result |
| --- | --- | --- |
| Saved receipt | Twelve state/current-source combinations exercise the real bot ingress handler. Only the three nonterminal states for the current input show the saved notice; the handler returns without execution or typing. | PASS |
| Degraded boundaries | The causal selection also covers connection refusal, timeouts, ambiguous 503, pre-write rejection, obsolete inputs and the actual source-order HTTP adapter. | PASS: 21 checks |
| Confirmed consumers | Bot preview, LibreChat bridge and voice preference tests run from the clean publication candidate. | PASS: 719 checks |
| Prior real Telegram surface | In the earlier isolated local candidate, Telegram Web showed the saved notice during the ordering dependency outage, followed by the recovered answer. Both persisted after real reload; the header was idle, delivery was committed and the acknowledgement outbox was empty. The adapter bytes match that loaded candidate. | PASS for that recorded local window |

The prior causal run failed to show the retained-input notice before this adapter change.
Its corrected selection passed. Exact source hashes, identifiers, screenshots and raw receipts
remain private.

## Findings

The clean publication candidate was tested locally. Its new package has not been installed in
the managed runtime by this publication task. No new external Telegram messages, provider calls,
runtime changes or full-project sweep were made. Prior live evidence supports the unchanged
adapter bytes; it does not prove deployment of this new publication commit or unrelated
LibreChat ordering and source-recovery work.

## Traceability

The `ingress-outage-and-idle-typing` journey in the linked case catalog owns outage wording,
retained inputs, recovery and idle presentation. This report covers the typed receipt adapter;
the separately pinned Core input implementation owns ordering and durable admission.

## Full-View Evidence Checklist

Bot source, bridge classification, current-source guard, owning docs and causal tests were
checked. The earlier real Telegram browser observation is retained below at its source scope.
Its delivery state, acknowledgement outbox and reload evidence support that observation; they
do not certify installation of the new publication commit.

## User-Grade Evidence

- Surface exercised: Earlier isolated Telegram Web browser path; the publication candidate received source and consumer checks.
- Real user path: A synthetic message met an ordering outage, showed a saved-input notice and later received its recovered answer.
- Visible outcome: The notice and recovered answer appeared; the header returned to idle.
- Expanded/detail state: Conversation and delivery state were inspected; a separate detail panel was not part of this case.
- Persistence/reload result: The notice and answer persisted after actual reload in that recorded local window.
- Backend/log/DB confirmation: Delivery was committed and the acknowledgement outbox was empty; exact receipts and identifiers stay private.
- Final model/runtime wording check: The adapter bytes match the earlier loaded source; no new publication deployment, provider or full-channel parity claim is made.
- Substitution check: Tests and source correspondence support retained user evidence; they do not replace fresh installed-path evidence where required.

## Public-Safety Review

Only synthetic observations, scoped conclusions and counts are published. Raw messages, account
and chat identifiers, credentials, screenshots, machine paths and operational logs remain private.
The report and changed source were included in the public-safety review.

The following retained evidence covers the separate intake and ordered-recovery candidate. It does
not replace the adapter publication recheck above or certify this new publication checkout.

## Retained intake and ordered-recovery evidence — 2026-10-25

QA: blast-radius. Result: **SCOPED PASS** on the loaded local candidate.
This covers Telegram intake, ordered recovery and confirmed consumers. It makes no public release,
Voice function, timer, or general readiness claim.

### Change and owning cases

The [Telegram requirements](../../../docs/requirements_and_learnings/03_Telegram_Bridge.md) and
[owning journeys](../cases.yaml) require durable, ordered input and truthful recovery without
replaying accepted actions. This report covers `ingress-outage-and-idle-typing` and the affected
rapid-correction portion of `telegram-main-parity`.

- Existing Message storage and ingress registration now precede the ordering dependency wait.
  Invalid preparation is refused before storage; source-only commands create no fake input.
- The exact monotonic ordering command has a native five-second deadline. A known recoverable
  retained receipt permits a saved-message notice. Unknown outcomes and terminal duplicates do
  not invite duplicate execution. The existing owner releases unused preparation leases for retry.
- Recovery prepares earlier retained inputs before admission and preserves the accepted source
  parent chain. Unbound native cancellation protects exact job identity from late startup metadata.
  Native source, effect, revision, permission and delivery fences remain active.

### Actual evidence

| Contract | Expected and observed result | Result |
| --- | --- | --- |
| Foreground reply | Real Telegram Web delivered the correct short arithmetic answer; native completion and transport acknowledgement agree. | PASS |
| Rapid correction | Three fresh messages produced one useful answer with the final two-bullet, at-home and screen-free constraints. It persisted after real reload. | PASS |
| Actual dependency outage | The existing Redis container was paused with its socket open. All three exact inputs and preparation were durable before the native ordering wait failed in about five seconds. The latest input showed the saved-message notice. | PASS |
| Deferred preparation | The live timeline captured all three preparing rows with zero lease, existing retry delay and unchanged failure-attempt count before the same container resumed. No input entered Main during the outage. | PASS |
| Ordered recovery | Existing recovery prepared the earlier sources, admitted the final source and published one native answer with explicit ordered ownership of all three. No earlier personal goal was replayed. | PASS |
| Source identity | Accepted source and parent hashes remained valid through publication and subsequent earlier-source continuations. Real source-edit controls still revoke changed authority. | PASS |
| Durable settlement | All three inputs completed with zero lease and no failure code after the original admitted lease. The exact Telegram delivery was committed; the ACK outbox was empty. | PASS |
| Visible result and persistence | The saved notice was followed by two useful bullets. Both remained after real Telegram reload. The bot header was idle, with no error or system spam. | PASS |
| Loaded artifact and process continuity | Running Core and the captured bot matched the frozen sources and rebuilt API. Core, bot, helper and the existing voice-gateway process kept their identities during the final pause/recovery window. | PASS for this local window |

An earlier rapid run exposed a cancellation identity race. The first actual outage run then exposed
an earlier-source parent re-anchor that correctly triggered native revocation. Both failed runs and
original records remain preserved. Fresh runs after the repairs passed; no historical row was patched.
Exact source IDs, process identities, hashes, screenshots and raw receipts remain private.

### Automated checks and limits

The final stream and source-owner selection passed 322 checks across memory, an owned temporary
Redis, source recovery, native response, serialization and Main context. This replaces the earlier
269-check cancellation selection. The typed input lifecycle passed 59 checks, replacing its earlier
51-check selection. The saved-notice selection passed 20 Python checks.

The final recovery and parent selections passed 53 unique public route checks plus one private
case using actual native parent methods. The Mongo preparation/query selection passed 46 checks.
These are separate selections, with no combined total. The earlier intake selection passed 195
checks before the later consumer repairs; its route overlap with the final selections is unknown.
Repeated and overlapping checks are not added.

The complete 195-test route bank exhausted the Jest heap and is **NOT PASSED**. Focused affected
checks ran in bounded batches. Three broader Python recovery fixtures failed identically against
old bytes and are not reported passed. Runtime-helper and cache-config proofs belong to their own
evidence and are not included in these counts.

No full-project sweep, public release, commit, push or component-pin update was run. Private
screenshots, raw source receipts, personal identifiers, logs and exact hashes remain outside this
public report.

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

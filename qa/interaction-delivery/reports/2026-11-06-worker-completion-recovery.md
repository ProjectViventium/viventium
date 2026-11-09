# Worker completion after file publication failure

## Summary

QA mode is blast radius. This report covers the local development candidate and
`worker-result-after-file-publication-failure` (PW-071, PW-076, PW-110).

Two completed workers had no terminal callback or Telegram delivery row. The native
runtime raised during file publication before saving the callback. The existing
recovery scan excluded their older origin-only work. A later 12.5-minute job on the
previous storage repair delivered one result with two attachments, so job duration
does not explain the earlier loss.

## Scope Run

The first live reproduction exposed two more boundaries. A queue notification tried
to publish a reference quoted in the original request and returned HTTP 500 after
accepting the job. The worker started and completed. Core accepted its terminal
callback and file manifest, but Main's follow-up returned a typed attachment
publication error and entered synthesis retry.

Only terminal callbacks render output references. The native file reader leaves
already-projected references to the publisher. An unavailable file in a worker
completion or a trusted Main callback response now leaves an explicit rejection,
while useful text and verified sibling files proceed. The renderer still checks the
same owner and run, and the foreground response retains strict publication errors.
Origin-only completions record their callback obligation in the terminal transaction
and clear it when the same generation reaches the existing outbox.

## Automated Evidence

The focused checks passed across the native runtime (300), Core (417), and Telegram
(77). They cover mixed and all-unavailable outputs, strict foreground behavior,
quoted original input, owner-scoped download, exact restart recovery after a
publication fault, and no legacy replay. Three broader account API assertions also
failed with the new recovery changes removed from the test import; two concern
read-side callback observations and one concerns a retained provider session.

Claude reviewed sanitized evidence and challenged partial results, crash recovery,
and historical replay. The repair uses the existing reconciliation and delivery
records and does not bulk resend older results or unknown transport attempts.

Exact runtime source fingerprints remain in the private evidence ledger.

In Telegram Desktop, Main acknowledged the synthetic job and answered the separate
arithmetic question while the worker was still running. The worker finished in
80.3 seconds. Telegram showed the result and one CSV 8.7 seconds later, with one
transport notice that the second file was unavailable. The result arrived without
a status request. The stored run, terminal outbox, Main message and Telegram
delivery ledger agree on one completed generation and one delivery. The imported
22-byte CSV matches the worker's SHA-256 and both expected rows. No callback
recovery obligation remained for the delivered run.

The local runtime, Core, Web and Playground health checks returned HTTP 200.
The Telegram download button could not be activated by Computer Use, so the byte
comparison used the exact host import linked to the delivered attachment. Older
unmarked jobs were left in place. This run does not certify public release or
live Voice delivery.

## Traceability

The [interaction-delivery case bank](../cases.yaml) owns worker-result-after-file-publication-failure; [parallel-work requirements](../../../docs/requirements_and_learnings/55_Parallel_Work_Orchestration.md) own once-only completion and useful partial results.

## Full-View Evidence Checklist

The retained evidence above identifies the selected source, tests, artifact and state checks, visible user path and remaining gaps. This format update does not renew that historical acceptance for the publication candidate.

## User-Grade Evidence

- Surface exercised: Telegram Desktop, an independently running Worker, the delivered file card and its host import.
- Real user path: Main answered a separate question while work ran, then Telegram showed the result and one available CSV without a status request.
- Visible outcome: One result, one CSV and one explicit unavailable-file notice appeared.
- Expanded/detail state: The selected delivery ledger and callback obligation settled once; the Desktop download control could not be activated.
- Persistence/reload result: The restart-recovery fault has deterministic coverage; this report records no separate live UI reload acceptance.
- Backend/log/DB confirmation: The run, terminal outbox, Main message and delivery ledger agree; imported bytes matched the delivered attachment reference.
- Final model/runtime wording check: Host-import byte comparison supports the file identity; it is not a successful Telegram Desktop download click.
- Substitution check: Automated checks, source review and model review support only their stated scopes; they do not replace the required visible, persistence or physical-audio evidence.

## Findings

The selected result-recovery path passed locally. Broader account API assertions and live Voice remain outside that acceptance.

## Public-Safety Review

Raw prompts, personal media, accounts, credentials, operational identifiers, source hashes, screenshots and logs remain private. Only sanitized behavior, bounded evidence and remaining gaps are published.

# Local handoff and context recovery — 2026-11-05

## Summary

QA: blast-radius. Overall: **PASS for the selected local repair paths**.
Broader voice/reliability acceptance remains **PARTIAL**. Local development candidate only;
no commit, pin or release claim.

## Findings

- An application resource cap rejected valid broker context just above 512 KiB before a worker
  started. Main then received no delegation tools. Removed both grant and deferred authorization
  resource byte checks. Complete authorized source stays intact; no replacement cap was added.
- A separate 500 ms observation timer discarded a valid native session budget and selected the
  smaller discovery allocation. Removed that wrapper. The existing result GET timeout and real
  request cancellation own the read. At most one result GET runs; preceding callback rows require
  only owner-local admission reads.
- Signed owner, tenant, turn, expiry, revocation, digest and allowed-tool checks remain. Native
  receipt validity and model capacity checks remain. No prompt, model, effort or role change.

## Scope Run

| Requirement / case | Expected | Actual |
| --- | --- | --- |
| Parallel Work `PW-014`, `PW-081` / selected browser and resource path of `PWK-011` | Main delegates complete authorized context to a native worker. | An accepted browser request reached its authorized worker and returned a result through the existing Web delivery path. Private source and result content are excluded from this report. |
| Main continuity / selected receipt and continuation path of `MC-UC-004` | A slow valid receipt must not become a smaller fallback allocation. | Live old-code observation expired at 502 ms. Final compiled helper retained the correct authenticated budget after a deliberately delayed read lasting 1,751 ms, with one GET. |
| Parallel Work `PW-018`, `PW-028` / selected follow-up and reload path | Another request can finish while independent work continues; results persist. | An independent question returned an answer while accepted work continued. A Telegram browser request returned its observed title, and completed results remained delivered after reload. |
| Parallel Work `PW-028`, `PW-081` / retained file presentation | Existing files can be shown in another authorized surface without regeneration. | The existing authorized file path returned retained output without regeneration. Downloaded bytes matched the selected source and remained available after reload. Private file classifications and content are omitted. |

## Automated Evidence

- Broker and deferred authorization: **271 passed**. Complete 600,000-byte context and 1 MiB
  resource mint, persist and hydration pass; ungranted resources stay excluded. The signed token
  contains a resource reference, not the large resources. Both old-code regression cases failed.
- Native receipt reader: **18 passed**, including the old-code 750 ms failure, slow callback
  ancestry, unavailable result, cancellation and foreign/stale/invalid identity refusals.
- Main context confirmed consumers: **365 passed**, including complete-source fit, unknown or
  overflowing capacity, alternate-route bounds and retained reviewed reconciliation.
- **654 focused checks passed.** Production package build clean; scoped diff checks clean.
  Managed Core reload loaded the final build. Native API process was unchanged.
- Final-source Telegram turns used the authenticated native session allocation. Native admission
  records report zero omitted messages and zero pruned tool payloads; formal native source/tool
  coverage remains `unproven`, so this is not a full native-history certification. Message/delivery
  state was retained privately. No failed or unfinished selected
  reply remained. Private screenshots, exact source hashes, logs, DB identities and file hashes
  are retained in the incident evidence; none is included in this public report.
- Claude review found no proved blockers after correcting its scan-count and HTTP-head assumptions
  against the actual control flow, reference transport and completed worker path.

## Limits of this result

This passes the selected local repair paths, not the full requirement banks or product. The exact
historical lookup duration was not recorded; the reproduced 500 ms defect proves the failure class.
The original question was replayed without resetting the conversation. Native calibration can
still rely on a prior observed ratio: turns with unproven source coverage do not refresh it.
Actual native admission remains authoritative and can reject overflow; this repair does not
certify calibration renewal. Source remains preserved when real capacity or authority is unavailable. Response-speed acceptance, existing saved-memory
errors and iPhone speaker behavior remain open; this change does not certify them. Nested source
is still local and unpinned. A local file-protocol page was not inspected through the browser
connector; the authenticated Web delivery surface was verified separately.

## Traceability

The [Main continuity cases](../cases.md) and [parallel-work cases](../../parallel-work/cases.yaml) own complete authorized handoff, responsive continuation and retained-file presentation.

## Full-View Evidence Checklist

The retained evidence above identifies the selected source, tests, artifact and state checks, visible user path and remaining gaps. This format update does not renew that historical acceptance for the publication candidate.

## User-Grade Evidence

- Surface exercised: Telegram and authenticated Web delivery, including browser download and reload.
- Real user path: Accepted browser work completed, an independent question answered while work continued, and selected files remained available.
- Visible outcome: Useful replies and retained output appeared through their existing delivery paths.
- Expanded/detail state: Authenticated capacity reads, exact source ownership and refusal cases were checked; full native-history coverage remained unproven.
- Persistence/reload result: Completed results and the selected downloaded file remained available after Web reload.
- Backend/log/DB confirmation: Compiled-helper reads, native admission and retained message/delivery state support the bounded result.
- Final model/runtime wording check: Selected repair-path acceptance does not certify fast response, calibration renewal or phone audio.
- Substitution check: Automated checks, source review and model review support only their stated scopes; they do not replace the required visible, persistence or physical-audio evidence.

## Public-Safety Review

Raw prompts, personal media, accounts, credentials, operational identifiers, source hashes, screenshots and logs remain private. Only sanitized behavior, bounded evidence and remaining gaps are published.

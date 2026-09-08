# Overlapping scheduled and ordinary answers

## Summary

Status: **PARTIAL**. Requirement `CC-035`; case `SCHED-021`, natural-continuity journey.

## Scope Run

A scheduled briefing and an ordinary answer completed concurrently and were both stored. Chat
selected the ordinary branch and hid the scheduled answer. The shared view had the same risk.
The fix projects adjacent trusted system results beside the selected ordinary branch, without
changing stored parents or native continuation authority. Existing branch controls remain usable;
an additive answer cannot claim the next user reply's parent.

## Automated Evidence

Actual local Chrome checks show both stored answers after reload and in a newly created anonymous
share. The control envelope stays hidden. A selected-branch, nonrecursive JSON export contains both
answers and no orphan parent links; internal structural rows have no prompt text or content.
Focused regression checks cover Chat/Share branch selection, composer ownership, and export
structure. The production frontend build and its existing browser compliance checks passed.

Candidate artifact tree digest:
`83e6d68364f9c40f941189fe2d4a72834b61a996816c8b6c77295c097f202d0f`.
Exact source, generated artifact, runtime, and private synthetic conversation receipts remain in
the private implementation evidence under `scheduled-result-visibility`.

## Findings

Open: repeat a fresh live overlap without reloading, then follow up through the composer; complete
the actual JSON reimport and branch-control journey. Chrome refused automated file selection
because its extension lacks file URL access. The exported structure and unit tests do not replace
that check. Installed native and Telegram parity remain separate open gates. This result does not
claim the complete scheduling or cognitive-continuity capability is accepted.

## Traceability

Scheduled result visibility -> CC-035 -> overlapping scheduled and ordinary answers -> SCHED-021
-> both results visible without changing branch authority -> local Chrome reload/share and export
checks -> live overlap, follow-up, JSON reimport, and channel parity remain open.

## Full-View Evidence Checklist

Reloaded Chat and anonymous Share visibility and export structure have supporting evidence.
Fresh overlap, composer follow-up, actual reimport, and complete branch controls remain open.

## User-Grade Evidence

- Surface exercised: local Chrome browser Chat and anonymous Share.
- Real user path: overlapping stored results were inspected after reload and in a new share; fresh overlap and follow-up remain open.
- Visible outcome: both stored answers appeared and the control envelope remained hidden.
- Expanded/detail state: complete branch-control interaction remains open.
- Persistence/reload result: both answers remained visible after reload; actual JSON reimport is unproved.
- Backend/log/DB confirmation: both answers were stored; export structural checks retained both without orphan parents.
- Final model/runtime wording check: the control envelope stayed hidden; a new live overlap remains unverified.
- Substitution check: source, export, and unit evidence do not replace the blocked actual JSON reimport or remaining visible journey.

## Public-Safety Review

This report contains sanitized behavior, public test scope, and a candidate artifact digest.
Exact conversations, native identities, generated artifacts, and private receipts stay private.

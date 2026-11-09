# Telegram round video notes — 2026-11-05

## Summary

QA scope is blast-radius. Result is a scoped live pass for spoken round notes.
Silent-note Telegram delivery remains open. The candidate is the local Telegram bridge source, loaded through the existing bot watchdog. Core and the native harness use
their existing photo ingress. Exact source hashes and runtime receipts stay private.

The [Telegram bridge requirements](../../../docs/requirements_and_learnings/03_Telegram_Bridge.md#telegram-attachments)
and [Telegram journey](../cases.yaml) cover CORE-002, CORE-007 and CC-048. Round notes
reuse the selected speech route and the owner-scoped image attachment. The bridge
prepares both from one download. Standard Telegram video uploads keep their own path.

## Scope Run

| Contract | Evidence | Result |
| --- | --- | --- |
| Local visual preparation | Real FFmpeg and Pillow produced ordered grids for spoken, silent and 60-second synthetic notes. The 60-second fixture produced 12 tiles in 85 ms on one local run. | PASS |
| Speech and degradation | Bridge tests verify one download, existing speech route selection, silent input, speech-only and image-only recovery, and current-source notices. A real decode classified the silent fixture as no speech. | PASS |
| Attachment ownership and recovery | Five focused Core ingress cases passed, including native photos, persisted attachment reuse and admitted-stream reuse. | PASS |
| Native visual interpretation | The configured GPT-6.1 Sol identified red then blue in separate one-shot tests of a single grid and 12 individual frames. It also read the silent card from the grid alone. The grid uses one attachment. | PASS |
| Loaded local bridge | The watchdog loaded a new bot process after the previous Telegram turn settled. Core, web and native health endpoints returned HTTP 200. Four component packaging checks passed. | PASS |
| Spoken round note in Telegram | A real 15-second note asked about a sequence of gestures without naming them. Telegram showed the transcript, one answer describing the gesture sequence and the optional audio attachment, all linked to the same note. Bridge logs show one download and 11 frames prepared in 131 ms. Core stored one owner-scoped JPEG whose hash matched the exact native image input. The native run completed and persisted one answer 5.45 seconds after receipt on this run. | PASS |
| Silent round note | The real bridge preparation, FFmpeg and audio decoder produced one image and no speech notice from the silent fixture, with a stub at the download boundary. GPT-6.1 Sol read its card in a separate test. No silent note was forwarded through the live Telegram chat. | PASS in local preparation and model checks. Live delivery not run. |

## Automated Evidence

The affected bridge selection passed 1,006 tests and 15 subtests. The broader Core
route run reached the default Node heap ceiling. The five affected ingress cases
were rerun in isolation. No full release sweep was run.

## Traceability

The [Telegram attachment requirements](../../../docs/requirements_and_learnings/03_Telegram_Bridge.md#telegram-attachments) and [video case bank](../cases.yaml) own one-download round-note preparation and admitted image input.

## Full-View Evidence Checklist

The retained evidence above identifies the selected source, tests, artifact and state checks, visible user path and remaining gaps. This format update does not renew that historical acceptance for the publication candidate.

## User-Grade Evidence

- Surface exercised: Real Telegram spoken round note, local FFmpeg/decoder preparation and native visual interpretation.
- Real user path: Telegram received a spoken note and showed its transcript, gesture answer and optional audio; no live silent note was forwarded.
- Visible outcome: The linked transcript, one answer and audio attachment appeared for the same spoken note.
- Expanded/detail state: Frame order, silent/degraded speech, attachment reuse and exact native input bytes were checked in their stated layers.
- Persistence/reload result: Core persisted one answer and its owned image; a separate live reload/restart journey was not recorded.
- Backend/log/DB confirmation: One-download logs, stored JPEG identity, native completion and loaded bridge checks support the spoken-note result.
- Final model/runtime wording check: Silent preparation and separate model interpretation do not establish silent-note Telegram delivery.
- Substitution check: Automated checks, source review and model review support only their stated scopes; they do not replace the required visible, persistence or physical-audio evidence.

## Findings

Spoken round-note delivery passed for the selected local path. Live silent-note delivery and a full release sweep remain unrun.

## Public-Safety Review

Raw prompts, personal media, accounts, credentials, operational identifiers, source hashes, screenshots and logs remain private. Only sanitized behavior, bounded evidence and remaining gaps are published.

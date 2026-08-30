# Telegram Photo Worker Handoff QA - 2026-08-21

## Summary

- Result: `PASS-LIVE` for the installed local photo-ingress slice.
- A real Telegram Desktop single-photo upload without a caption produced one content-aware answer.
- A real three-photo album whose transport names were all `photo.jpg` reached the configured
  GlassHive-backed Main as three distinct ordered files and produced one complete answer.
- The escaped parser failure, placeholder-only worker input, same-name aliasing, missing workspace
  files, and duplicate follow-up presentation each received structural fixes and regressions.
- This is a dirty installed-checkout result. Clean nested commits, parent pins, clean install, and
  public release parity remain `PARTIAL`.

## Scope Run

| Case | Result | What ran |
| --- | --- | --- |
| `TGDOC-005` | `PASS-LIVE` | Three-photo Telegram album coalesced into one logical turn in Telegram order |
| `TGDOC-008` | `PASS-LIVE` | One post-restart uncaptioned photo and one same-name three-photo album reached the active worker as real files |
| `TGDOC-009` | `PASS-LIVE` | Final album persisted and delivered one assistant result; the duplicate follow-up window stayed quiet |
| Cross-owner file-ID isolation | `PASS-AUTOMATED` | Exact owner/file-ID lookup resolves one unique source and fails closed on absent or ambiguous input |
| Clean release artifact | `PARTIAL` | Active checkout was rebuilt and restarted; clean clone/install and component-pin parity were not run |

## Traceability

`Telegram photo -> shared attachment contract -> owner-scoped raw upload -> ordered upload projection
-> GlassHive conversation workspace -> model reads exact bytes -> one Main presentation -> one
Telegram delivery`

- Requirement: [`03_Telegram_Bridge.md`](../../../docs/requirements_and_learnings/03_Telegram_Bridge.md),
  Telegram Attachments.
- Principle: [`01_Key_Principles.md`](../../../docs/requirements_and_learnings/01_Key_Principles.md),
  native capability reuse, truthful results, and no prompt-specific routing.
- Cases: `TGDOC-005`, `TGDOC-008`, and `TGDOC-009` in this folder's `cases.md`.
- Expected result: images remain images; exact bytes and order reach the configured provider or
  worker; one logical request is presented once.
- Actual result: visible Telegram output, upload records, worker bundle/files, provider completion,
  Mongo presentation, delivery acknowledgement, logs, and automated regressions agreed.

## Full-View Evidence Checklist

| Evidence surface | Result |
| --- | --- |
| Real user surface | Telegram Desktop sent one photo and one three-photo album |
| Visible outcome | Exact image facts returned; no parser error, placeholder warning, or duplicate answer |
| Bridge logs | Album grouped once with three files and one bridge submission |
| Upload persistence | Three distinct owner-scoped upload rows retained independent file IDs despite equal filenames |
| Worker projection | Ordered entries resolved by file ID; filename fallback was not used |
| Worker filesystem | Three materialized JPEG files had distinct byte counts and SHA-256 values |
| Provider runtime | Album completed without fallback; the post-restart single photo recovered from one classified quota failure and completed once |
| Mongo/delivery | One user row and one assistant row; one Telegram delivery acknowledgement |
| Refresh/persistence | Result remained visible after the complete follow-up window; cleanup later removed only synthetic local QA state |
| Failure/recovery | Earlier real failures reproduced parser rejection, placeholder-only input, missing workspace files, same-name aliasing, and duplicate presentation before each fix |
| Release boundary | Installed dirty source passed; clean build/install/pin/rollback remains unrun |

## User-Grade Evidence

- Surface exercised: Telegram Desktop against the installed local production runtime.
- Real user path: send one synthetic card as a photo without a caption; then send three distinct
  synthetic cards as one album and ask for each visible label and code in order.
- Visible outcome: the single photo returned its exact label/code once; the album returned all three
  exact label/code pairs in numeric order in one assistant bubble.
- Expanded/detail state: the private worker workspace and ordered upload bundle were inspected after
  the visible result; all three sources were present as separate files.
- Persistence/reload result: the accepted album had one persisted assistant row and one delivery
  acknowledgement. No second assistant row appeared during the background follow-up window.
- Local/external prerequisite state: Telegram bot, LibreChat, GlassHive, MongoDB, Meilisearch, and
  recall/RAG were active. Synthetic non-personal images were used.
- Evidence retrieval classification, if applicable: file retrieval was available and exact; failed
  earlier attempts were missing/aliased source files, not an empty successful result.
- Fallback path, if applicable: the album needed no fallback. The post-restart single photo's first
  provider run reported `provider_quota_exhausted`; the configured retry completed and produced one
  visible answer without a duplicate or generic error bubble.
- Backend/log/DB confirmation: the album worker bundle contained three ordered entries and the
  materialized files had three distinct byte hashes; the provider request completed; Mongo and the
  Telegram delivery ledger recorded one result. The post-restart single photo persisted one upload,
  one user row, one assistant row, and one delivery after the classified recovery.
- Final model/runtime wording check: the answer reported only facts visible in the supplied images
  and did not claim unavailable files were read.
- Substitution check: logs, DB rows, worker files, provider completions, and tests are supporting
  evidence, not substitutes for the real Telegram Desktop actions and visible results above.

## Automated Evidence

- LibreChat photo upload, route, follow-up, and adjacent Core/Telegram suites: `363/363` passed in
  the final affected run.
- Full Telegram bot suite: `457/457` passed after the photo changes.
- GlassHive upload projection, conversation provider, and host-runtime materialization suites:
  complete focused set passed, including the live-shaped ID-only same-name album regression.
- The escaped cases include trusted-image parser bypass, ordered repeated filenames, absent and
  cross-owner file-ID failure, conversation workspace materialization, and canonical duplicate
  follow-up suppression while distinct follow-ups remain allowed.
- The active local stack returned HTTP 200 on its API, LibreChat web, and call-playground health
  surfaces after activation.

## Findings

- Root cause 1: the trusted Telegram JPEG entered a text-document parser that cannot parse
  `image/jpeg`. Fix: trusted bridge images bypass text extraction and retain raw owner-scoped bytes.
- Root cause 2: worker upload context existed but was not projected into the GlassHive conversation
  bundle. Fix: one canonical upload projection is shared by provider and MCP paths.
- Root cause 3: conversation-mode host runtime returned before materializing declared files. Fix:
  mission and conversation paths use the same bounded materialization helper.
- Root cause 4: file-ID-bearing album entries fell back to `photo.jpg`, so newest-file selection
  aliased three inputs into one. Fix: durable owner/file ID resolves first and filename fallback is
  forbidden when an ID exists.
- Root cause 5: a background follow-up repeated the correct Main answer with only punctuation and
  spacing changes. Fix: canonical exact duplicates are suppressed in the shared follow-up service,
  before persistence and delivery.
- Hygiene: exact private preimages were saved. Thirteen synthetic QA messages and sixteen upload
  files were removed from local Mongo/search/recall; continuity was rebuilt from thirty retained
  real revisions; the pre-photo working memory was restored; the recall corpus contains no synthetic
  image markers; and the contaminated Main/compactor workers were terminated. The post-restart
  proof then removed its exact two messages and one image, rebuilt recall, retained the protected
  natural Telegram pair, left saved memory unchanged, and terminated only its two linked workers.
  Provider audit rows and remote Telegram transport evidence were retained.
- Remaining gap: broad Telegram attachment parity still includes more file types and degraded paths
  in older cases. This report closes the photo/album/worker slice, not the full release program.

## Public-Safety Review

- [x] Synthetic non-personal image content only.
- [x] No private chat transcript, screenshot, account ID, conversation/message/session ID, raw
  provider request ID, token, cookie, email, hostname, or machine name.
- [x] No local absolute path or private cleanup manifest location.
- [x] Raw images, screenshots, logs, DB rows, and backups remain outside the public repository.
- [x] Public evidence uses counts, behavior, and sanitized conclusions only.

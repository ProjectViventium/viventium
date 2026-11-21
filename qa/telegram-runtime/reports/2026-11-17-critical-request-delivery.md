# Critical request delivery, local 2026-11-17

## Summary

Status: **PARTIAL**. The tested Telegram file-delivery and recovery paths work on the active local
candidate. Full product readiness and all historical requirements are not signed off.

QA mode: **full**, bounded to the local Main request lifecycle: conversation, correction, uploads,
Native continuation, files, delivery, failure, replay, persistence and restart.

## Scope Run

This is retained evidence from the dated local candidate. It does not certify the later public
prompt bytes or current publication candidate.

## Traceability

| Requirement and use case | Expected result | Actual evidence | Status |
| --- | --- | --- | --- |
| [Telegram delivery](../../../docs/requirements_and_learnings/03_Telegram_Bridge.md), `TR-038`: finished Native work | Byte-exact result identity; file facts beside it | Repaired changed result hashing and multimodal preparation. Saved result and original reply recovered without rerunning the work. | PASS |
| `TR-038`: resend existing files | Verified publisher, owner and stored bytes survive | Both saved files reached Telegram. Original and resent stored bytes match. Final CSV-only request sent exactly one requested document, with no retry. | PASS |
| `TR-038`: silent Main with owed files | Deliver the exact owned files without requiring filler text | Repaired file-only dispatch authorization. Real failed send recovered through its normal retry after restart. | PASS |
| `TR-038`: replay and goal aliases | One publication and unchanged channel receipts | Concurrent real alias replays created no new Main messages. Both later saved-result replays kept the same delivery and receipts. | PASS |
| `TR-038`: missing or unavailable source | Truthful failure and recovery; no silent loss | Missing upload was refused, then read after upload. Temporary source-proof failure now propagates for recovery. Changed or foreign sources remain refused. | PASS for tested paths |
| `TR-038`: callback and file authorization | Reject unsigned, malformed, expired and foreign requests | Real HTTP rejections and replay checks; cross-owner file requests returned 403 without file bytes. Active send permits remain protected. | PASS |
| [Prompt architecture](../../../docs/requirements_and_learnings/49_Prompt_Architecture_and_Token_Efficiency.md): style and receipt truth | Own prose follows style; literal sources stay exact; acceptance differs from delivery | The private Voice v4 and Tools v35 were compared, dry-run, applied narrowly and checked in Workbench, live config and acknowledged Native authority. The observed punctuation belongs to those private bytes. The public Voice v4 instead applies saved preferences; current controlled Codex comparisons pass, while the configured Claude comparison remains quota-blocked. | PASS for observed cases; broader alignment remains open |
| `TR-038`: reload and restart | Recover saved work and accept a new request | Verified API child restarted through its normal supervisor; health recovered; new real requests and attachments completed. | PASS |

Owners changed: shared Native coordinator presentation, Core file preparation and callback delivery,
the Telegram bridge's unsent-claim recovery, and the registered Main prompts. Models, tools,
personal settings and other agents were preserved. No text scrubber or user-intent routing rule was
added. These are local changes; no commit, push or release was made.

## Automated Evidence

- Combined Telegram suite: **1,609 passed and 15 subtests passed**. Three tests previously left a
  fake image module loaded during collection. Removing those stubs allowed the whole bank to run
  together; the earlier isolated per-file run also passed.
- Shared Main presentation, Native source and dispatch: **126 passed**, including file-only
  positive proof and changed-owner, changed-file, missing-file and Voice rejection cases.
- Core callback/context bank: **222 passed**. Latest retained-file bank: **70 passed**. The two
  unchanged continuation consumer suites also passed their final compatible repair batch.
- Registered prompt and scheduler contracts: **47 passed**. The affected shared package built.
- Tools v35 comparison: **44 completed generations**, 11 identical unblocked cases, old/proposed
  on each configured primary and fallback at the configured effort. Completion is not a semantic
  quality pass. Human review found primary-model question and brevity failures in both variants.
  The automated semantic judge was not run.

## Findings

1. **Performance:** the final long-chat request took about 209 seconds to reach its attachment.
   Native logs explicitly reported provider compaction. Continuity survived it; acceptable latency
   has not been proved. Trace native history and context refresh before proposing a change; retain
   quality and original source context.
2. **Proactive truth:** an existing scheduled Main message asked whether files had arrived after
   delivery. It came from a separate scheduled conversation under the earlier Tools prompt. Trace
   current cross-conversation continuity and delivery facts, then test the real scheduled path on
   the final prompt. Do not treat a newer interactive success as that proof.
3. **Primary-model alignment:** some isolated acknowledgments still expose receipt checks and ask
   unnecessary questions. Preserve the failed rubrics. Assess their source and current state before
   further prompt changes; do not silently switch models or alter personal settings.
4. **UI evidence:** actual Telegram text and attachment bubbles were observed, including reopening
   the chat. The final GUI download could not be operated with the available native controls.
   Stored-byte parity supports delivery but does not replace that download check. Local HTML
   browser navigation was denied, and the web client required login. These UI checks are blocked.
5. **Provider evidence:** one earlier expanded style case was refused by Claude safeguards on both
   variants. It remains blocked and was not reformulated or retried. Direct configured-model
   comparisons do not prove automatic fallback on every live provider failure.
6. **Broader audit:** current-chat prompts were preserved privately and reconciled, but every
   historical source and the complete product have not been qualified by this repair.

Raw prompts, chats, identifiers, hashes, logs, database snapshots and transport receipts remain in
private evidence. No private source or screenshot is included here.

## Subsequent provider interruption

The next reported failure had a different cause. Transcription and durable handoff succeeded,
then the primary provider rejected the conversational reply at its weekly account quota. Native
terminal recovery changed the known public provider class to a generic failure and omitted the
already committed work receipt from FINAL. Telegram therefore reported the whole request as
failed while its accepted operation continued. The worker later completed and delivered its
captioned image, text and audio exactly once. Those results were observed in the real chat.

The repair preserves the public provider class through Mongo, FINAL and replay, while retaining
the stronger Native source checks. Ordinary and Native response routes now share the exact receipt
projection. Telegram distinguishes a proved accepted new operation from a reply that failed before
acceptance and uses its existing durable follow-up. Explicit stop, uncertain action and foreign
scope remain fenced. No provider was remapped and no execution deadline or context cap was added.

Final compatible checks: **26 Native terminal integration cases, 198 shared API cases, 123 schema
cases, 167 request-controller cases, and 1,618 Telegram cases plus 15 subtests passed**. Shared
packages built. The new receipt module passed lint. Full-file lint still reports errors in other
previously edited sections, so this is not an all-clean lint claim. The captured Telegram component matches tested source; the normal supervisors
reloaded Core and handed off to the new poller. A new real message completed on the configured
fallback at its configured effort, with a saved Native result and committed delivery, and remained
after chat reopen. The owner-requested heartbeat addition was verified in the original worker's
tool readback and current scheduler state; its original prompt, cadence and channels were preserved.

`TR-039` remains **PARTIAL**: the new post-acceptance interruption wording has deterministic
cross-layer evidence, but a second live post-acceptance provider failure was not induced. The
primary account quota, optional classifier account billing/authentication failures, and unavailable
browser coverage in the original worker remain external or open gates. The broader audit and the
other open gates above remain open. This is a local repair, not a release or full-product sign-off.


## Full-View Evidence Checklist

| Evidence surface | Actual evidence and limit |
| --- | --- |
| Requirements, code and cases | Telegram TR-038/TR-039, shared result/file authorization, durable receipts and registered prompt owners above. |
| Tests, logs and state | Scoped cross-layer checks, stored-byte identity, retained result and acknowledged delivery/replay state; raw proof private. |
| Generated/running artifacts | Original local assembled component and normal supervisor reload checked. Not the later public source candidate. |
| Real user and visible path | Telegram bubbles and chat reopen observed; final GUI download and broader browser evidence remain blocked. |

## User-Grade Evidence

- Surface exercised: Native Telegram chat, local runtime and supporting HTTP/API checks on the dated candidate.
- Real user path: Ask for files, resend a selected result, recover a failed send, replay and reopen the chat.
- Visible outcome: Selected files and later fallback reply were observed. Final GUI download was not completed.
- Expanded/detail state: Telegram text and file bubbles were observed; unavailable GUI controls prevented the final download interaction.
- Persistence/reload result: Chat reopen retained the observed result; supervisor restart recovered service and accepted new requests.
- Backend/log/DB confirmation: Exact stored-byte parity, result/receipt identity and replay state support the observations. Raw hashes and owner state remain private.
- Final model/runtime wording check: Historical private prompt comparisons have named alignment failures and quota limits; deterministic post-acceptance wording does not prove a second live interruption or the later public prompt.
- Substitution check: Stored-byte parity, tests, logs and model review support delivery but do not substitute for the blocked GUI download, current public-policy model comparison or broader live journeys.

## Public-Safety Review

- [x] No raw private prompts, model replies, owner/customer data, attachments, state or screenshots.
- [x] No credentials, personal identity, private URLs, machine paths or operational identifiers.
- [x] Sanitized dated outcomes; current-candidate and incomplete-user-path limits remain explicit.

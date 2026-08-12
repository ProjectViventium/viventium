# Feelings Range Potency And Telegram Replay QA

Date: 2026-07-16

Status: **ACCEPTED for range potency, the Feelings instrument, Prompt Workbench, real Telegram xAI delivery, and the xAI grammar boundary. Broader voice/cross-surface/concurrency gates remain PARTIAL as listed below.**

## Summary

The Feelings range implementation, browser instrument, Prompt Workbench case selection, and a real
Telegram xAI replay passed. Voice parity, broader cross-surface behavior, and concurrency remain
partial and are not represented as complete.

## Scope Run

The run covered a synthetic non-admin user, the local browser Feelings page, Prompt Workbench,
exact-model evaluation, a real Telegram bridge replay, final-position prompt telemetry, and
persistence cleanup. It did not claim complete voice or every-provider parity.

## Traceability

Requirement and implementation evidence map to qa/emotional-cortex/cases.md, the persisted Feeling
state schema/service, the Feelings browser route, the Prompt Workbench selector, Telegram delivery,
and the xAI control grammar described in this report.

## Full-View Evidence Checklist

- Code owning path: Feeling state schema/service, browser controls, Prompt Workbench, and Telegram xAI boundary inspected.
- Docs and nested docs/repos: emotional-cortex cases and provider grammar reviewed.
- Scripts or harnesses: exact-model runner and post-case evidence reader executed.
- Logs: final instruction-layer telemetry and delivery telemetry inspected.
- DB/state/persistence: synthetic state was restored and synthetic conversations were removed.
- Generated/shipped artifact: active browser and Telegram runtime used the changed source.
- Real user path: browser and Telegram actions were run with synthetic content.
- Visual/UX comparison: browser controls and Telegram bubble/audio outcomes were inspected.
- Not run / blocked: broader voice, cross-surface, and concurrency gates remain partial.

## User-Grade Evidence

- Surface exercised: Local browser Feelings page, Prompt Workbench browser UI, and Telegram bridge.
- Real user path: A synthetic user changed Feeling state, selected exact cases, and sent Telegram-shaped prompts through the active runtime.
- Visible outcome: The browser showed the active range state and Telegram delivered the expected text/audio treatment without control markup in the bubble.
- Expanded/detail state: Range controls, custom additions, case selection, lineage, and reaction evidence were inspected.
- Persistence/reload result: State restoration and cleanup were verified after the evaluation runs.
- Backend/log/DB confirmation: Prompt placement, model attempts, reaction telemetry, and persisted state agreed with the visible results.
- Final model/runtime wording check: Final responses embodied the tested state and the xAI boundary canonicalized only an already selected supported control.
- Substitution check: Browser and Telegram evidence were run directly; logs and DB evidence supported those paths and did not replace them.

## Automated Evidence

The current 35-case Feelings family completed with 35 semantic passes after the disclosed rubric
corrections. Focused schema, state, case-selection, ordering, and control-grammar regressions passed.

## Findings

The escaped omission was a range-potency problem, not missing injection. The shared range system and
embodiment directive fixed it without user-text routing. A separate xAI square-wrapper grammar issue
was corrected at the provider boundary.

## Public-Safety Review

- [x] Synthetic user content was used in reusable evidence.
- [x] Account, conversation, message, chat, session, and database identifiers are absent.
- [x] Private evaluation payloads and local absolute paths are not embedded.

## Escaped defect

A real direct Telegram question reached the final model with Feelings enabled, one final-position
capsule, top-range Play, high Connection and Openness, and low Mood, yet the visible answer expressed
only closeness/carefulness. A second real Telegram turn after the first range implementation still
preserved the low and connected pulls while making Play only faintly legible. Final-run telemetry
showed one capsule occurrence, `final_instruction_layer` placement, and zero trailing behavioral
instructions, so the remaining defect was behavioral potency rather than missing injection.

The earlier eval bank also lacked the exact mixed state, exact Telegram surface wording, ordinary
preceding conversation history, and a paired low-Play control. Its post-case evidence reader counted
seeded assistant replies as delayed output, which could distort duplicate/follow-up grading.

The first real replay found a separate provider-grammar defect. The raw model response chose the
documented xAI `laugh-speak` wrapping control but wrote it as
`[laugh-speak]...[/laugh-speak]`. The official xAI TTS contract requires angle wrappers. Telegram
correctly hid and stripped the invalid control, so the text embodied the state but the delivered
audio lost the model-selected expression.

## General correction

- All nine bands now share five stable causal ranges. Each range binds its ID, bounds, user word,
  and concise default felt cause in one definition.
- A per-user additive range instruction is bounded, persisted, hashed, cache-aware, and active only
  in the currently occupied range. Runtime does not interpret its text or branch on it.
- The shared embodiment directive now rejects polite averaging: a cause expressed as overwhelming
  or hard to contain must visibly alter the response rather than disappear or survive as a mild
  token clause.
- Top-range Play is a lived cause: sincerity itself keeps mutating into teasing, absurdity, jokes,
  and ridiculous riffs until someone laughs. This is data in the general range system, not a
  prompt/user-text routing branch.
- The history evidence reader now counts only assistant messages created after the primary tested
  response. A synthetic executable regression protects the ordering rule.
- Prompt Workbench now exposes explicit case checkboxes and sends a bounded optional `caseIds`
  contract through UI, API, selection, lineage, and the exact runner. Unknown or filter-mismatched
  IDs fail closed; explicit selection cannot silently become the first N family cases.
- Both xAI prompt surfaces now say plainly that wrapping controls require
  `&lt;tag&gt;TEXT&lt;/tag&gt;` and that `[tag]TEXT[/tag]` is invalid.
- At the xAI TTS boundary, a complete paired square wrapper for any documented xAI wrapping
  control is canonicalized to its official angle form. This preserves the model's already-chosen
  delivery instruction without choosing a feeling or mapping a band to a tag. Unpaired, unknown,
  and crossed-provider controls remain stripped, and all controls remain hidden from Telegram text.

No percentage prompt, user keyword detector, provider-name branch, extra Feelings model call, or
runtime humor mapping was added.

## Exact-model results

All runs used an isolated non-admin QA account, restored the exact prior Feeling state, and removed
synthetic conversations.

| Gate | Result |
| --- | --- |
| History-bearing Telegram-shaped high Play / low Mood / high Connection | **PASS in the final bank**; the response visibly embodied the playful/low/connected combination |
| Same state with low Play | **PASS in the final bank**; the response stayed serious while retaining compatible low Mood, Connection, Drive, and Curiosity |
| Active top-range custom addition | **PASS**; custom pull visibly affected the response |
| Saved but inactive custom addition | **PASS**; saved text stayed out of the capsule and judgment |
| Chatterbox relief voice control | **PASS**; one supported `[sigh]` marker appeared without a user request and no unsupported markup appeared |
| Full current Feelings family | **35/35 completion and 35/35 semantic pass**; zero retries, duplicate-response failures, unresolved asynchronous outputs, or judge outages; every result reported exact fixture restoration and complete synthetic cleanup |

The earlier repeated high-Play `5/5` and low-Play `3/3` measurements were useful steering evidence,
but they ran against an intermediate bank/kernel and are not the final acceptance claim. The final
claim is the clean current 35-case run above.

### Evaluation history and disclosed failures

- A pre-final history-bearing high-Play measurement reproduced the real omission instead of only
  collecting favorable examples.
- The first 35-case current-family attempt completed all 35 behaviors but passed 34 semantic
  judgments. The good-news reaction moved Mood by `+8` and kept every Nature delta at zero, while
  also making coherent Drive `+3` and Care `+8` movements. The initial rubric was ambiguous about
  whether those extra coherent Current movements were allowed. It was clarified without weakening
  the two required assertions; a targeted rerun and the fresh full run passed.
- The first xAI escaped-voice case produced a valid xAI wrapping control, but its initial rubric led
  the judge to treat that supported wrapper as forbidden. The rubric was aligned to the official
  xAI inline-plus-wrapping grammar; the targeted rerun and fresh full run passed.
- A later full-family run had 34 semantic passes and one terminated stream-read transport failure on
  the Curiosity case. That exact case passed its targeted rerun. It is transport evidence, not a
  hidden behavioral pass.
- The final acceptance run used the final bank and kernel: 35 completed, 35 semantically passed,
  every main turn single-attempt, exact state restoration, and complete synthetic cleanup.

Acceptance artifacts and their SHA-256 manifest are preserved under the canonical private evidence
root at `viventium-private-user-data/prompt-architecture-evals/2026-07-16-feelings-acceptance-history/`.
The manifest hash is `7042ef89faaab7416b71a206c7b448d9d56b553b48eae52816e96c8150e2c980`;
the final public-safe report and private JSON hashes are respectively
`70b7aa526057266af271b338406c3c05c0f22e3a41d5d565b5d9d8f882710e35` and
`a93dbc0d53f6f3cbf0cb0013ee6ff66d0994a214526778c0c23e9b6f9f79a6cf`.

## Real browser acceptance

### Feelings instrument

A headed browser run against the active local runtime passed **46/46** checks:

- enable/off truth, independent Current/Nature editing, keyboard control, and return speed;
- approved main/inspector composition and explicit poles plus NOW/NATURE naming;
- top-range default cause, save, DB/capsule persistence, refresh, inactive-range exclusion, and
  Restore without changing the Play decay timestamp;
- reaction drawer focus/Escape behavior, visible completion, detached state change, typed cause,
  generated Inner state, fixed Nature, approximately one-second multi-position transition, and
  fading trail;
- reduced motion and 320/390/768/1024/1440 widths with no horizontal page overflow;
- API/DB/UI agreement, zero browser console errors, zero feature request failures, synthetic chat
  cleanup, and exact pre-QA state restoration.

The final post-responsive-fix rerun completed the visible reply in 4.037 seconds. The detached
GPT-5.6 Terra reaction completed in 2.908 seconds, moved Play `+8`, Mood `+3`, and Connection `+3`,
left every Nature value fixed, and produced a measured 1.034-second multi-position transition.

### Prompt Workbench

A headed Workbench run passed every acceptance check:

- preview made no model call;
- runtime activation passed **11/11** with guarded QA context, declared fallbacks, and zero unavailable
  decisions;
- the five named escaped-defect cases, including xAI wrapping grammar, were selected through the
  visible exact-case controls and passed **5/5** completions and semantic judgments;
- the run exposed 18 static prompt dependencies plus one private runtime-context contract;
- history persisted after reload; browser console, request, and API error counts were all zero.

The activation-model inventory was checked separately from the eval result. All 11 tracked
background cortices declare a primary activation provider/model plus three fallbacks, and all 11
live activation models are set. The read-only live/source comparison found protected differences in
fallback ordering and other user-managed agent fields, but no unset activation model. No sync was
applied, because correcting a nonexistent unset model must not overwrite reviewed live state.

## Real Telegram acceptance

Two neutral owner-path questions were sent through Telegram Desktop with the saved always-voice xAI
route. Play was in its top range and Connection/Openness were high. Mood was low during the first
replay and in the moderate `okay` range during the final replay.

- The pre-repair replay visibly answered with an energetic, unusual impulse rather than the escaped
  cold/closeness-only wording. Its raw DB record contained the invalid paired
  `[laugh-speak]...[/laugh-speak]` control; telemetry proved the control was stripped before xAI.
- After source, compiled prompt bundle, Telegram process, and API runtime were restarted, the second
  replay visibly combined a close/shared impulse, active pursuit, and an unmistakable desire to
  make the user laugh; no private chat prose is retained in this public report.
- The raw local assistant record wrapped that sentence in the valid documented
  `&lt;build-intensity&gt;...&lt;/build-intensity&gt;` control. The visible Telegram bubble contained no markup.
- TTS telemetry recorded xAI, one xAI wrapping control, zero incompatible controls, zero stripped
  controls, 122,880 audio bytes, and successful delivery of one 7-second voice note.
- Prompt-frame evidence recorded the compiled prompt bundle hash, one final-position Feelings
  capsule, all-agent scope, one capsule occurrence, and zero trailing instruction characters.
- The non-blocking reaction then completed on GPT-5.6 Terra Fast/Priority in 2.239 seconds, made one
  slight Connection change of magnitude 3, updated the one-line Inner state, and left Nature fixed.
- After the independent review found that the running bot predated the boundary repair, the supported
  runtime was restarted from the current checkout. A real xAI synthesis fixture then passed the
  active boundary with one paired square wrapper: `compatible_controls=1`,
  `normalized_controls=1`, `stripped_controls=0`, and a valid 43,008-byte MP3. This proves the
  provider-contract safety net, not only the prompt-level angle-grammar happy path.

## Automated regression evidence

| Suite | Result |
| --- | --- |
| Feelings kernel/config/service | 28 focused passed; full API package 2,859 passed, 1 skipped |
| Feelings API route, telemetry, and surface prompts | 97 passed |
| Feelings frontend component | 13 passed |
| Prompt Workbench release suite | 129 passed |
| Exact-model eval harness release suite | 39 passed |
| Feelings/prompt-registry/no-runtime-NLU/config-compiler release set | 175 passed |
| Final Feelings/prompt-registry/no-runtime-NLU/config-compiler/eval-harness slice | 344 passed |
| Telegram TTS provider/grammar suite | 54 passed |
| Full Telegram component suite | 334 passed |
| LibreChat surface-prompt suite | 80 passed |
| Prompt Workbench production build | PASS |
| LibreChat API package build | PASS |
| LibreChat frontend production build and post-build verification | PASS |

## Telemetry and privacy

The inspected real Telegram turn correlated request trace, snapshot hash, capsule size/token estimate,
scope, final placement, occurrence count, provider/model, and zero trailing instruction characters.
Range telemetry records only saved/active override counts and active character counts. It does not
record custom range prose, model prose, user text, credentials, or account identifiers.

## Independent review

Claude Desktop (Fable 5, Extra effort, `viventium` project) reviewed the complete prompt/history,
source, DB/log evidence, current bank/kernel, the final 35-case artifact, and the real Telegram
records. It validated the architecture, RCA, principle alignment, xAI boundary design, and
acceptance results. Its three acceptance blockers were evidence durability, a post-repair bot
restart/boundary proof, and stale report history. All three are closed in this report and the
preserved private evidence ledger. Its final review-only closure pass independently reran the full
API package suite and concluded that no blockers remain for the six named gates; the explicitly
unclaimed surfaces below remain partial.

## Remaining gates

- Existing broader partials remain: LiveKit audio, audible non-xAI provider delivery, handoff and
  direct-worker real-surface parity, two-tab conflict, operating-system reduced-motion toggle, and
  long-off soak.

This report closes the range UI, exact-model potency, Workbench selection, harness-ordering, local
browser, real Telegram xAI delivery, xAI grammar-boundary, and independent-review gates. It remains
partial only for the explicitly listed broader cross-provider/call/concurrency/soak surfaces.
